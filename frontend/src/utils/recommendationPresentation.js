const RECOMMENDATION_STATUSES = ["pending", "in_progress", "completed", "dismissed"];

export function getRecommendationQueueState({ datasetId, loading, error, result }) {
  if (!datasetId) return "no_dataset";
  if (loading) return "loading";
  if (error) return "error";
  if (!isValidRecommendationPage(result)) return "unavailable";
  return result.total === 0 ? "empty" : "populated";
}

function isValidRecommendationPage(result) {
  if (!result || typeof result !== "object" || Array.isArray(result) || !Array.isArray(result.data)) return false;
  if (!Number.isInteger(result.limit) || result.limit < 1) return false;
  if (!Number.isInteger(result.offset) || result.offset < 0) return false;
  if (!Number.isInteger(result.count) || result.count !== result.data.length) return false;
  if (!Number.isInteger(result.total) || result.total < 0) return false;
  if (result.count > result.limit || result.offset + result.count > result.total) return false;
  if (typeof result.has_more !== "boolean" || result.has_more !== (result.offset + result.count < result.total)) return false;
  if (!isRecommendationStatusCounts(result.status_counts)) return false;

  return result.data.every((item) => (
    item && typeof item === "object" && !Array.isArray(item)
    && typeof item.id === "string" && item.id.trim().length > 0
    && typeof item.learner_id === "string" && item.learner_id.trim().length > 0
    && RECOMMENDATION_STATUSES.includes(item.status)
    && typeof item.action === "string" && item.action.trim().length > 0
    && typeof item.reason === "string" && item.reason.trim().length > 0
    && (item.rule_id == null || (typeof item.rule_id === "string" && item.rule_id.trim().length > 0))
  ));
}

export function isRecommendationStatusCounts(counts) {
  return Boolean(counts && typeof counts === "object" && !Array.isArray(counts)
    && RECOMMENDATION_STATUSES.every((status) => Number.isInteger(counts[status]) && counts[status] >= 0));
}

export function getRecommendationStatusCounts(result, rows) {
  return isRecommendationStatusCounts(result?.status_counts)
    ? result.status_counts
    : countRecommendationStatuses(rows);
}

export function countRecommendationStatuses(rows) {
  return (Array.isArray(rows) ? rows : []).reduce((counts, item) => {
    if (RECOMMENDATION_STATUSES.includes(item?.status)) counts[item.status] += 1;
    return counts;
  }, { pending: 0, in_progress: 0, completed: 0, dismissed: 0 });
}
