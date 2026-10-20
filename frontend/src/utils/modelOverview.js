export function formatModelMetric(key, value) {
  if (value === null || value === undefined) return "Not available";
  if (["precision", "recall", "f1", "roc_auc", "pr_auc_average_precision", "decision_threshold"].includes(key)) {
    return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(1)}%` : "Not available";
  }
  return String(value);
}

export function confusionMatrixRows(matrix) {
  const labels = matrix?.labels;
  const values = matrix?.rows_actual_columns_predicted;
  if (!Array.isArray(labels) || !Array.isArray(values) || values.length !== labels.length) return null;
  if (values.some((row) => !Array.isArray(row) || row.length !== labels.length || row.some((value) => !Number.isFinite(value)))) return null;
  return labels.map((actual, index) => ({ actual, values: values[index] }));
}

export function modelStatusLabel(status) {
  const labels = {
    loaded: "Loaded successfully",
    unavailable: "Unavailable",
    not_checked: "Not checked",
    sample_scored: "Sample scored",
    input_schema_mismatch: "Input schema incompatible",
    model_unavailable: "Unavailable",
    not_available: "Not available",
    not_generated: "Not generated",
    not_implemented: "Not implemented",
    available: "Available",
  };
  return labels[status] || "Not available";
}

export function hyperparameterEntries(configuration) {
  if (!configuration || typeof configuration !== "object") return [];
  return Object.entries(configuration);
}

export function overviewState({ loading, error, result }) {
  if (loading) return "loading";
  if (error) return "error";
  return result ? "ready" : "unavailable";
}
