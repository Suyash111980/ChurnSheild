export function overviewMetricValue(value, { loading = false } = {}) {
  if (value !== null && value !== undefined) return value;
  return loading ? "Loading…" : "Unavailable";
}

export function overviewErrorMessage(error) {
  if (error?.status === 401) return `HTTP 401: ${error.detail || "Your session could not be authenticated. Sign in again, then retry."}`;
  if (error?.status === 403) return `HTTP 403: ${error.detail || "This account is not authorized to view platform administration."}`;
  if (error?.status === 503) return `HTTP 503: ${error.detail || "The backend could not read required platform metadata. Check deployed database migrations and backend database permissions."}`;
  return error?.status
    ? `HTTP ${error.status}: Platform workspace information could not be loaded. Retry or contact the backend administrator.`
    : "Platform workspace information could not be loaded. Check the backend connection and retry.";
}

export function datasetStatusMessage(overview, { loading = false, error = false } = {}) {
  if (error) return "Dataset status is unavailable because the platform overview request failed.";
  if (loading) return "Loading dataset status…";
  const statuses = overview?.dataset_status_counts;
  if (!statuses || Object.keys(statuses).length === 0) return "No datasets recorded.";
  return null;
}
