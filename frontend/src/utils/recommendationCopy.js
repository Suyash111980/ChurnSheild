const RULE_COPY = {
  no_observed_vle_activity_by_cutoff: {
    title: "Review learner engagement",
    reason: "No platform activity was recorded by the observation cutoff. This can reflect access or recording issues and does not by itself establish disengagement.",
    action: "Check that the learner can access the learning platform, then offer a supportive check-in and help finding course resources.",
  },
  assessment_without_submission_recorded_by_cutoff: {
    title: "Offer assessment support",
    reason: "No assessment submission was recorded by the observation cutoff. The available data does not establish whether the learner missed, deferred, or submitted through another route.",
    action: "Confirm the assessment status and deadline with the learner, ask whether support is needed, and share relevant submission guidance.",
  },
};

function displayText(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function formatRecommendation(item = {}) {
  const technicalRule = [item.rule_id, item.reason, item.action]
    .filter((value) => typeof value === "string")
    .map((value) => value.trim().split(/[:\s]/, 1)[0])
    .find((value) => Object.hasOwn(RULE_COPY, value));
  const copy = RULE_COPY[technicalRule] || {};
  const riskValue = item.prediction?.risk_category || item.risk_category;
  const risk = ["low", "medium", "high"].includes(String(riskValue || "").toLowerCase())
    ? String(riskValue).toLowerCase()
    : null;
  const probabilityValue = item.prediction?.risk_probability ?? item.risk_probability;
  const probability = probabilityValue != null && Number.isFinite(Number(probabilityValue))
    && Number(probabilityValue) >= 0 && Number(probabilityValue) <= 1
    ? Number(probabilityValue)
    : null;

  return {
    title: displayText(copy.title) || displayText(item.action) || "Review learner support",
    reason: displayText(copy.reason) || displayText(item.reason) || "No supporting rationale was recorded.",
    action: displayText(copy.action) || displayText(item.action) || "Review the saved evidence and decide whether a supportive follow-up is appropriate.",
    priority: risk ? risk[0].toUpperCase() + risk.slice(1) : "Unavailable",
    risk,
    probability,
    modelVersion: displayText(item.prediction?.model_version),
    technicalReason: displayText(item.reason),
    ruleId: displayText(item.rule_id) || technicalRule || null,
  };
}
