import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  contributionBar,
  contributionDirection,
  featureLabel,
  formatContribution,
  formatObservedValue,
  rankContributions,
} from "../src/utils/rootCausePresentation.js";

describe("Root Cause presentation helpers", () => {
  it("labels known features and falls back to readable title case without losing keys", () => {
    assert.equal(featureLabel("code_module"), "Course Module");
    assert.equal(featureLabel("vle_clicks_day_8_cutoff"), "VLE Activity from Day 8 to Cutoff");
    assert.equal(featureLabel("an_unrecognized_feature"), "An Unrecognized Feature");
    assert.equal(featureLabel(""), "Unknown feature");
  });

  it("provides a dedicated readable label for every canonical model input", () => {
    const canonicalFeatures = [
      "code_module", "code_presentation", "num_of_prev_attempts", "studied_credits",
      "module_presentation_length", "registration_record_present", "registration_by_cutoff",
      "registration_day_at_cutoff", "registration_date_missing", "assessments_due_by_cutoff",
      "assessment_submissions_by_cutoff", "assessment_late_submissions_by_cutoff",
      "assessments_without_submission_recorded_by_cutoff", "assessment_banked_results_by_cutoff",
      "assessment_submission_rate_by_cutoff", "vle_total_clicks_by_cutoff", "vle_active_days_by_cutoff",
      "vle_distinct_resources_by_cutoff", "vle_clicks_day_0_7", "vle_clicks_day_8_cutoff",
      "vle_has_activity_by_cutoff", "vle_days_since_last_activity_at_cutoff",
    ];
    assert.equal(canonicalFeatures.length, 22);
    for (const feature of canonicalFeatures) assert.notEqual(featureLabel(feature), feature, feature);
  });

  it("formats identifiers, confirmed indicators, units, counts and relative dates", () => {
    assert.equal(formatObservedValue("code_module", "GGG"), "GGG");
    assert.equal(formatObservedValue("code_presentation", "2014B"), "2014B");
    assert.equal(formatObservedValue("registration_record_present", 1), "Yes");
    assert.equal(formatObservedValue("registration_by_cutoff", false), "No");
    assert.equal(formatObservedValue("vle_has_activity_by_cutoff", true), "Yes");
    assert.equal(formatObservedValue("assessment_submissions_by_cutoff", 12), "12 submissions");
    assert.equal(formatObservedValue("num_of_prev_attempts", 3), "3 previous attempts");
    assert.equal(formatObservedValue("studied_credits", 30), "30 credits");
    assert.equal(formatObservedValue("module_presentation_length", 241), "241 days");
    assert.equal(formatObservedValue("registration_day_at_cutoff", -4), "Day -4 relative to presentation start");
    assert.equal(formatObservedValue("vle_days_since_last_activity_at_cutoff", 0), "0 days before cutoff");
    assert.equal(formatObservedValue("assessment_submission_rate_by_cutoff", 0.5), "50%");
  });

  it("distinguishes missing, zero and false values", () => {
    assert.equal(formatObservedValue("studied_credits", null), "Not recorded");
    assert.equal(formatObservedValue("studied_credits", undefined), "Not recorded");
    assert.equal(formatObservedValue("num_of_prev_attempts", 0), "0 previous attempts");
    assert.equal(formatObservedValue("registration_date_missing", 0), "No");
    assert.equal(formatObservedValue("unknown_flag", false), "false");
    assert.equal(formatObservedValue("unknown_number", 0), "0");
  });

  it("formats signed contribution values without treating them as percentages", () => {
    assert.equal(formatContribution(-0.07527), "−0.0753");
    assert.equal(formatContribution(0.0198), "+0.0198");
    assert.equal(formatContribution(0.00247), "+0.0025");
    assert.equal(formatContribution(-0.03729), "−0.0373");
    assert.equal(formatContribution(0), "0.0000");
    assert.equal(formatContribution(0.00005), "+0.00005");
    assert.equal(formatContribution(-0.00001), "−0.00001");
    assert.equal(formatContribution("not numeric"), "Unavailable");
  });

  it("describes positive-class SHAP direction and zero distinctly", () => {
    assert.match(contributionDirection(0.1).label, /toward predicted withdrawal/);
    assert.match(contributionDirection(-0.1).label, /away from predicted withdrawal/);
    assert.match(contributionDirection(0.00001).label, /Very small increase/);
    assert.match(contributionDirection(-0.00001).label, /Very small decrease/);
    assert.equal(contributionDirection(0).label, "No contribution to model output");
    assert.equal(contributionDirection(null).kind, "unknown");
  });

  it("ranks persisted explanations and scales bars relative to the largest contribution", () => {
    const rows = [
      { feature_name: "small", contribution: 0.1 },
      { feature_name: "large", contribution: -0.5 },
      { feature_name: "zero", contribution: 0 },
    ];
    assert.deepEqual(rankContributions(rows).map((row) => row.feature_name), ["large", "small", "zero"]);
    assert.equal(contributionBar(-0.5, 0.5), 50);
    assert.equal(contributionBar(0.1, 0.5), 10);
    assert.equal(contributionBar(0, 0.5), 0);
  });
});
