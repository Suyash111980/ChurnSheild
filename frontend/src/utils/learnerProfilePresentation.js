export function rankPersistedExplanations(explanations) {
  if (!Array.isArray(explanations)) return [];
  return explanations
    .filter((item) => item && typeof item.feature_name === "string" && item.contribution != null && item.contribution !== "" && Number.isFinite(Number(item.contribution)))
    .map((item, index) => ({ ...item, _sourceIndex: index, _magnitude: Math.abs(Number(item.contribution)) }))
    .sort((left, right) => right._magnitude - left._magnitude || left._sourceIndex - right._sourceIndex)
    .map(({ _sourceIndex, _magnitude, ...item }) => item);
}

export function buildRiskEvidenceSummary(explanations, limit = 3) {
  const count = Number.isInteger(limit) && limit > 0 ? limit : 3;
  return rankPersistedExplanations(explanations).slice(0, count);
}

export function scopeLearnerRecommendations(recommendations, learnerId, datasetId) {
  if (!Array.isArray(recommendations) || learnerId == null) return [];
  return recommendations.filter((item) => {
    if (!item || String(item.learner_id) !== String(learnerId)) return false;
    const relation = Array.isArray(item.learners) ? item.learners[0] : item.learners;
    if (!datasetId) return Boolean(relation?.dataset_id);
    return Boolean(relation?.dataset_id) && String(relation.dataset_id) === String(datasetId);
  });
}
