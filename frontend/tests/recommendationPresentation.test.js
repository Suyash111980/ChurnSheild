import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { countRecommendationStatuses, getRecommendationQueueState, getRecommendationStatusCounts } from "../src/utils/recommendationPresentation.js";
import { formatRecommendation } from "../src/utils/recommendationCopy.js";

const page = (data = [], overrides = {}) => ({
  data,
  limit: 20,
  offset: 0,
  count: data.length,
  total: data.length,
  has_more: false,
  status_counts: { pending: 0, in_progress: 0, completed: 0, dismissed: 0 },
  ...overrides,
});

const recommendation = (overrides = {}) => ({
  id: "recommendation-1",
  learner_id: "learner-1",
  prediction_id: "prediction-1",
  rule_id: "no_observed_vle_activity_by_cutoff",
  action: "Offer a supportive check-in",
  reason: "Observed no VLE activity by cutoff.",
  status: "pending",
  ...overrides,
});

describe("persisted recommendation queue presentation", () => {
  it("keeps loading, error, missing response, empty, and populated states distinct", () => {
    assert.equal(getRecommendationQueueState({ datasetId: null }), "no_dataset");
    assert.equal(getRecommendationQueueState({ datasetId: "d", loading: true }), "loading");
    assert.equal(getRecommendationQueueState({ datasetId: "d", error: new Error("API failed"), result: { data: [], total: 0 } }), "error");
    assert.equal(getRecommendationQueueState({ datasetId: "d", result: null }), "unavailable");
    assert.equal(getRecommendationQueueState({ datasetId: "d", result: { data: [] } }), "unavailable");
    assert.equal(getRecommendationQueueState({ datasetId: "d", result: page() }), "empty");
    assert.equal(getRecommendationQueueState({ datasetId: "d", result: page([recommendation()]) }), "populated");
  });

  it("rejects inconsistent pagination and malformed recommendation records", () => {
    assert.equal(getRecommendationQueueState({
      datasetId: "d", result: page([], { total: 3 }),
    }), "unavailable");
    assert.equal(getRecommendationQueueState({
      datasetId: "d", result: page([recommendation()], { count: 0 }),
    }), "unavailable");
    assert.equal(getRecommendationQueueState({
      datasetId: "d", result: page([recommendation({ action: "" })]),
    }), "unavailable");
    assert.equal(getRecommendationQueueState({
      datasetId: "d", result: page([recommendation({ status: "unknown" })]),
    }), "unavailable");
    assert.equal(getRecommendationQueueState({
      datasetId: "d", result: page([], { status_counts: undefined }),
    }), "unavailable");
    assert.equal(getRecommendationQueueState({
      datasetId: "d", result: page([recommendation({ prediction: { risk_category: "critical" } })]),
    }), "unavailable");
  });

  it("allows legacy null rule IDs while validating new rule IDs", () => {
    assert.equal(getRecommendationQueueState({
      datasetId: "d", result: page([recommendation({ rule_id: null })]),
    }), "populated");
    assert.equal(getRecommendationQueueState({
      datasetId: "d", result: page([recommendation({ rule_id: " " })]),
    }), "unavailable");
  });

  it("uses persisted status totals across pages and falls back to current rows", () => {
    const rows = [{ status: "pending" }];
    assert.deepEqual(getRecommendationStatusCounts(page(rows, {
      total: 21, has_more: true,
      status_counts: { pending: 12, in_progress: 5, completed: 3, dismissed: 1 },
    }), rows), { pending: 12, in_progress: 5, completed: 3, dismissed: 1 });
    assert.deepEqual(getRecommendationStatusCounts({ status_counts: { pending: -1 } }, rows), {
      pending: 1, in_progress: 0, completed: 0, dismissed: 0,
    });
  });

  it("counts only statuses present in the returned page", () => {
    assert.deepEqual(countRecommendationStatuses([
      { status: "pending" }, { status: "pending" }, { status: "in_progress" },
      { status: "completed" }, { status: "dismissed" }, { status: "unknown" },
    ]), { pending: 2, in_progress: 1, completed: 1, dismissed: 1 });
  });

  it("accepts server-wide status totals independently from the current page", () => {
    assert.equal(getRecommendationQueueState({
      datasetId: "d",
      result: page([recommendation()], {
        total: 21,
        has_more: true,
        status_counts: { pending: 11, in_progress: 5, completed: 3, dismissed: 2 },
      }),
    }), "populated");
  });
});


describe("human-readable persisted recommendation copy", () => {
  it("translates the saved platform activity rule without claiming disengagement", () => {
    const result = formatRecommendation(recommendation({
      action: "technical action", reason: "no_observed_vle_activity_by_cutoff: No VLE activity recorded (observed vle_has_activity_by_cutoff=0)",
    }));
    assert.equal(result.title, "Review learner engagement");
    assert.match(result.reason, /does not by itself establish disengagement/);
    assert.match(result.action, /Check that the learner can access/);
    assert.match(result.technicalReason, /^no_observed_vle_activity_by_cutoff:/);
    const legacy = formatRecommendation(recommendation({
      rule_id: null,
      reason: "no_observed_vle_activity_by_cutoff: no activity recorded",
    }));
    assert.equal(legacy.title, "Review learner engagement");
  });

  it("translates assessment evidence without assuming the learner missed it", () => {
    const result = formatRecommendation(recommendation({
      rule_id: "assessment_without_submission_recorded_by_cutoff",
      reason: "assessment_without_submission_recorded_by_cutoff: no submission recorded",
    }));
    assert.equal(result.title, "Offer assessment support");
    assert.match(result.reason, /does not establish whether the learner missed/);
    assert.match(result.action, /Confirm the assessment status/);
  });

  it("uses only available risk context and keeps unknown rule data intact", () => {
    const missing = formatRecommendation(recommendation({ rule_id: "unknown_rule", prediction: null }));
    assert.equal(missing.priority, "Unavailable");
    assert.equal(missing.probability, null);
    assert.equal(missing.title, "Offer a supportive check-in");
    const saved = formatRecommendation(recommendation({
      prediction: { risk_category: "high", risk_probability: 0.73, model_version: "rf-v1" },
    }));
    assert.equal(saved.priority, "High");
    assert.equal(saved.probability, 0.73);
    assert.equal(saved.modelVersion, "rf-v1");
    assert.equal(formatRecommendation(recommendation({ prediction: { risk_probability: 1.3 } })).probability, null);
  });
});
