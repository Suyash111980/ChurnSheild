import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildRiskEvidenceSummary, rankPersistedExplanations, scopeLearnerRecommendations } from "../src/utils/learnerProfilePresentation.js";

describe("learner profile evidence and recommendation mapping", () => {
  const explanations = [
    { id: "a", feature_name: "studied_credits", feature_value: 60, contribution: -0.2 },
    { id: "b", feature_name: "vle_clicks_by_cutoff", feature_value: 0, contribution: 0.4 },
    { id: "c", feature_name: "registration_by_cutoff", feature_value: 1, contribution: 0.1 },
    { id: "d", feature_name: "code_module", feature_value: "AAA", contribution: -0.4 },
  ];

  it("ranks by absolute persisted contribution and preserves ties and observed values", () => {
    assert.deepEqual(rankPersistedExplanations(explanations).map((item) => item.id), ["b", "d", "a", "c"]);
    assert.equal(rankPersistedExplanations(explanations)[0].feature_value, 0);
  });

  it("limits the compact evidence summary without altering the complete explanation", () => {
    assert.deepEqual(buildRiskEvidenceSummary(explanations, 3).map((item) => item.id), ["b", "d", "a"]);
    assert.equal(rankPersistedExplanations(explanations).length, 4);
    assert.deepEqual(buildRiskEvidenceSummary([{ feature_name: "x", contribution: "invalid" }]), []);
  });

  it("keeps only recommendations explicitly associated with the profile learner", () => {
    const rows = [
      { id: "r1", learner_id: "learner-a", learners: { dataset_id: "dataset-a" } },
      { id: "r2", learner_id: "learner-b", learners: { dataset_id: "dataset-a" } },
      { id: "r3", learner_id: "learner-a", learners: { dataset_id: "dataset-b" } },
      { id: "r4", learner_id: "learner-a" },
    ];
    assert.deepEqual(scopeLearnerRecommendations(rows, "learner-a", "dataset-a"), [rows[0]]);
    assert.deepEqual(scopeLearnerRecommendations([rows[3]], "learner-a", "dataset-a"), []);
    assert.deepEqual(scopeLearnerRecommendations(rows, null), []);
  });
});
