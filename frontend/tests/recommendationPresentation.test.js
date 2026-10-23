import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { countRecommendationStatuses, getRecommendationQueueState, getRecommendationStatusCounts } from "../src/utils/recommendationPresentation.js";

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
});
