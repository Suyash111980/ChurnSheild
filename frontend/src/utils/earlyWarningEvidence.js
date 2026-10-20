export function getEarlyWarningEvidenceItems(row) {
  const explanations = Array.isArray(row?.latest_explanations) ? row.latest_explanations : [];
  const contributions = explanations
    .filter((item) => typeof item?.feature_name === "string" && item.contribution != null && item.contribution !== "" && Number.isFinite(Number(item.contribution)))
    .map((item) => ({
      feature_name: item.feature_name,
      feature_value: item.feature_value,
      has_feature_value: Object.hasOwn(item, "feature_value"),
      contribution: Number(item.contribution),
      kind: "explanation",
    }));
  if (contributions.length) return contributions;

  const reason = typeof row?.latest_recommendation?.reason === "string"
    ? row.latest_recommendation.reason.trim()
    : "";
  return reason ? [{ feature_name: "Saved recommendation reason", feature_value: reason, contribution: null, kind: "reason" }] : [];
}

export function describeEarlyWarningEvidence(row) {
  const explanations = getEarlyWarningEvidenceItems(row);
  const contributions = explanations
    .filter((item) => item.kind === "explanation")
    .map((item) => {
      const observed = item.has_feature_value
        ? `observed ${JSON.stringify(item.feature_value)}`
        : "observed value unavailable";
      return `${item.feature_name} (${observed}; contribution ${item.contribution > 0 ? "+" : ""}${item.contribution.toFixed(3)})`;
    });
  if (contributions.length) return contributions.join("; ");
  return explanations[0]?.feature_value || "No saved evidence";
}

export function summarizeEarlyWarningEvidence(row, limit = 3) {
  const count = Number.isInteger(limit) && limit > 0 ? limit : 3;
  return getEarlyWarningEvidenceItems(row)
    .map((item, index) => ({ ...item, index, magnitude: item.kind === "explanation" ? Math.abs(item.contribution) : -1 }))
    .sort((left, right) => right.magnitude - left.magnitude || left.index - right.index)
    .slice(0, count)
    .map(({ index, magnitude, ...item }) => item);
}
