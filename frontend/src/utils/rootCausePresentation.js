const FEATURE_LABELS = {
  code_module: "Course Module",
  code_presentation: "Course Presentation",
  num_of_prev_attempts: "Previous Attempts",
  studied_credits: "Registered Study Credits",
  module_presentation_length: "Course Duration",
  registration_record_present: "Registration Record Available",
  registration_by_cutoff: "Registered by Cutoff",
  registration_day_at_cutoff: "Registration Timing",
  registration_date_missing: "Registration Date Missing",
  assessments_due_by_cutoff: "Assessments Due by Cutoff",
  assessment_submissions_by_cutoff: "Assessment Submissions",
  assessment_late_submissions_by_cutoff: "Late Assessment Submissions",
  assessments_without_submission_recorded_by_cutoff: "Assessments Without a Submission Recorded",
  assessment_banked_results_by_cutoff: "Banked Assessment Results",
  assessment_submission_rate_by_cutoff: "Assessment Submission Rate",
  vle_total_clicks_by_cutoff: "VLE Clicks by Cutoff",
  vle_active_days_by_cutoff: "VLE Active Days by Cutoff",
  vle_distinct_resources_by_cutoff: "Distinct VLE Resources by Cutoff",
  vle_clicks_day_0_7: "VLE Activity in the First 8 Days",
  vle_clicks_day_8_cutoff: "VLE Activity from Day 8 to Cutoff",
  vle_has_activity_by_cutoff: "VLE Activity Recorded",
  vle_days_since_last_activity_at_cutoff: "Days Since Last VLE Activity",
};

const BINARY_FEATURES = new Set([
  "registration_record_present",
  "registration_by_cutoff",
  "registration_date_missing",
  "vle_has_activity_by_cutoff",
]);
const COUNT_FEATURES = new Set([
  "num_of_prev_attempts",
  "assessments_due_by_cutoff",
  "assessment_submissions_by_cutoff",
  "assessment_late_submissions_by_cutoff",
  "assessments_without_submission_recorded_by_cutoff",
  "assessment_banked_results_by_cutoff",
  "vle_total_clicks_by_cutoff",
  "vle_active_days_by_cutoff",
  "vle_distinct_resources_by_cutoff",
  "vle_clicks_day_0_7",
  "vle_clicks_day_8_cutoff",
]);

export function featureLabel(featureName) {
  if (typeof featureName !== "string" || !featureName.trim()) return "Unknown feature";
  return FEATURE_LABELS[featureName] || featureName
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function finiteNumber(value) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string" && value.trim() !== "") {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }
  return null;
}

function compactNumber(value) {
  return new Intl.NumberFormat("en", { maximumFractionDigits: 4 }).format(value);
}

export function formatObservedValue(featureName, value) {
  if (value === null || value === undefined || value === "") return "Not recorded";
  if (featureName === "code_module" || featureName === "code_presentation") return String(value);
  if (BINARY_FEATURES.has(featureName) && typeof value === "boolean") return value ? "Yes" : "No";

  const numeric = finiteNumber(value);
  if (numeric === null) return String(value);
  if (BINARY_FEATURES.has(featureName)) {
    if (numeric === 1) return "Yes";
    if (numeric === 0) return "No";
  }
  if (featureName === "studied_credits") return `${compactNumber(numeric)} credits`;
  if (featureName === "module_presentation_length") return `${compactNumber(numeric)} days`;
  if (featureName === "registration_day_at_cutoff") return `Day ${compactNumber(numeric)} relative to presentation start`;
  if (featureName === "vle_days_since_last_activity_at_cutoff") return `${compactNumber(numeric)} days before cutoff`;
  if (COUNT_FEATURES.has(featureName)) {
    const noun = featureName === "num_of_prev_attempts" ? "previous attempts"
      : featureName === "vle_total_clicks_by_cutoff" || featureName.startsWith("vle_clicks_") ? "clicks"
        : featureName === "vle_active_days_by_cutoff" ? "active days"
          : featureName === "vle_distinct_resources_by_cutoff" ? "resources"
            : featureName === "assessment_late_submissions_by_cutoff" ? "late submissions"
              : featureName === "assessments_without_submission_recorded_by_cutoff" ? "assessments without a submission recorded"
                : featureName === "assessment_banked_results_by_cutoff" ? "banked results"
                  : featureName === "assessments_due_by_cutoff" ? "assessments due" : "submissions";
    return `${compactNumber(numeric)} ${noun}`;
  }
  if (featureName === "assessment_submission_rate_by_cutoff") return `${new Intl.NumberFormat("en", { style: "percent", maximumFractionDigits: 1 }).format(numeric)}`;
  return String(value);
}

export function formatContribution(value) {
  const numeric = finiteNumber(value);
  if (numeric === null) return "Unavailable";
  if (numeric === 0) return "0.0000";

  // Four decimals for ordinary values; add precision for small values so a
  // real nonzero contribution is never presented as zero.
  const decimals = Math.min(12, Math.max(4, Math.ceil(-Math.log10(Math.abs(numeric))) + 1));
  const rounded = Number(numeric.toFixed(decimals));
  if (rounded === 0) return `${numeric < 0 ? "−" : "+"}${numeric.toExponential(2)}`;
  const rendered = Math.abs(rounded).toFixed(decimals).replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
  return `${numeric < 0 ? "−" : "+"}${rendered}`;
}

export function contributionDirection(value) {
  const numeric = finiteNumber(value);
  if (numeric === null) return { kind: "unknown", label: "Direction unavailable" };
  if (numeric === 0) return { kind: "neutral", label: "No contribution to model output" };
  if (Math.abs(numeric) < 0.0001) {
    return numeric > 0
      ? { kind: "positive", label: "Very small increase toward predicted withdrawal" }
      : { kind: "negative", label: "Very small decrease away from predicted withdrawal" };
  }
  return numeric > 0
    ? { kind: "positive", label: "Increases model output toward predicted withdrawal" }
    : { kind: "negative", label: "Decreases model output away from predicted withdrawal" };
}

export function rankContributions(explanations) {
  return [...(Array.isArray(explanations) ? explanations : [])].sort((left, right) =>
    Math.abs(finiteNumber(right?.contribution) ?? 0) - Math.abs(finiteNumber(left?.contribution) ?? 0));
}

export function contributionBar(value, maximum) {
  const numeric = finiteNumber(value) ?? 0;
  return maximum > 0 ? Math.min(50, Math.abs(numeric) / maximum * 50) : 0;
}
