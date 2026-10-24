export const EARLY_WARNING_PAGE_SIZE = 100;

export function nextEarlyWarningOffset(offset, result) {
  if (!result?.has_more) return offset;
  const pageSize = Number.isInteger(result.limit) && result.limit > 0
    ? result.limit
    : EARLY_WARNING_PAGE_SIZE;
  return offset + pageSize;
}

export function previousEarlyWarningOffset(offset, result) {
  const pageSize = Number.isInteger(result?.limit) && result.limit > 0
    ? result.limit
    : EARLY_WARNING_PAGE_SIZE;
  return Math.max(0, offset - pageSize);
}

export function earlyWarningSummary(summary) {
  const safeCount = (value) => Number.isInteger(value) && value >= 0 ? value : null;
  const distribution = summary?.risk_distribution;
  return {
    learnerRecords: safeCount(summary?.total_learner_records),
    savedPredictions: safeCount(summary?.learners_with_prediction),
    coverage: typeof summary?.prediction_coverage === "number" && Number.isFinite(summary.prediction_coverage)
      ? summary.prediction_coverage
      : null,
    high: safeCount(distribution?.high),
    medium: safeCount(distribution?.medium),
    low: safeCount(distribution?.low),
  };
}