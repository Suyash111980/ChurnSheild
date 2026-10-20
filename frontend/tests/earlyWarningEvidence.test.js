import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { describeEarlyWarningEvidence, getEarlyWarningEvidenceItems, summarizeEarlyWarningEvidence } from "../src/utils/earlyWarningEvidence.js";

describe("early-warning evidence uses persisted rationale only", () => {
  it("shows stored explanation contributions with canonical feature names", () => {
    assert.equal(describeEarlyWarningEvidence({ latest_explanations: [
      { feature_name: "vle_total_clicks_by_cutoff", feature_value: 14, contribution: 0.12345 },
      { feature_name: "studied_credits", feature_value: null, contribution: -0.5 },
    ] }), "vle_total_clicks_by_cutoff (observed 14; contribution +0.123); studied_credits (observed null; contribution -0.500)");
  });

  it("returns persisted evidence entries for a compact expandable presentation", () => {
    assert.deepEqual(getEarlyWarningEvidenceItems({ latest_explanations: [
      { feature_name: "studied_credits", feature_value: 60, contribution: -0.25 },
    ] }), [{
      feature_name: "studied_credits",
      feature_value: 60,
      has_feature_value: true,
      contribution: -0.25,
      kind: "explanation",
    }]);
  });

  it("selects the three strongest persisted signals for the compact warning row", () => {
    const row = { latest_explanations: [
      { feature_name: "first", feature_value: 1, contribution: 0.01 },
      { feature_name: "strongest", feature_value: 2, contribution: -0.8 },
      { feature_name: "middle", feature_value: 3, contribution: 0.4 },
      { feature_name: "third", feature_value: 4, contribution: 0.2 },
    ] };
    assert.deepEqual(summarizeEarlyWarningEvidence(row).map((item) => item.feature_name), ["strongest", "middle", "third"]);
    assert.equal(getEarlyWarningEvidenceItems(row).length, 4);
  });

  it("falls back to a saved recommendation reason, not its action", () => {
    assert.equal(describeEarlyWarningEvidence({ latest_recommendation: {
      action: "Offer support", reason: "No submission was recorded by day 30.",
    } }), "No submission was recorded by day 30.");
  });

  it("does not invent evidence when no persisted rationale exists", () => {
    assert.equal(describeEarlyWarningEvidence({ latest_recommendation: { action: "Check in" } }), "No saved evidence");
  });
});
