export function createDatasetService(request) {
  return {
    uploadDataset: (formData) => request("/datasets/upload", { method: "POST", body: formData }),
    listDatasets: (params = {}) => {
      const query = new URLSearchParams({ limit: "100", offset: "0", ...params });
      return request(`/datasets?${query}`);
    },
    previewDataset: (formData) => request("/datasets/preview", { method: "POST", body: formData }),
    getDataset: (id) => request(`/datasets/${encodeURIComponent(id)}`),
    deleteDataset: (id, options = {}) => request(`/datasets/${encodeURIComponent(id)}`, { ...options, method: "DELETE" }),
    retryDataset: (id, formData) => request(`/datasets/${encodeURIComponent(id)}/retry`, { method: "POST", body: formData }),
    reprocessDataset: (id, formData) => request(`/datasets/${encodeURIComponent(id)}/reprocess`, { method: "POST", body: formData }),
  };
}

export function datasetDeletionFeedback(outcome) {
  if (outcome.status === "cancelled") return null;
  return {
    message: "Dataset deleted successfully.",
    error: outcome.status === "deleted_refresh_failed"
      ? `The dataset was deleted, but the list could not refresh: ${outcome.error?.message || "refresh failed"}`
      : "",
  };
}

export async function confirmAndDeleteDataset({
  dataset,
  selectedDatasetId,
  confirm,
  deleteDataset,
  refresh,
  onDeleting,
}) {
  const confirmed = confirm(
    `Delete dataset “${dataset.dataset_name}”? Its saved learner records, feature snapshots, predictions, explanations, and recommendations will be permanently removed together.`,
  );
  if (!confirmed) return { status: "cancelled" };

  onDeleting?.();
  await deleteDataset(dataset.id);
  try {
    await refresh(dataset.id === selectedDatasetId ? undefined : selectedDatasetId);
    return { status: "deleted" };
  } catch (error) {
    return { status: "deleted_refresh_failed", error };
  }
}

export async function submitDatasetRevision({
  datasetId,
  status,
  file,
  retryDataset,
  reprocessDataset,
  refresh,
  onResponse,
  onRefreshError,
}) {
  const formData = new FormData();
  formData.append("file", file);
  const submit = status === "failed" ? retryDataset : reprocessDataset;
  const response = await submit(datasetId, formData);
  onResponse?.(response);
  try {
    await refresh(response?.data?.id || datasetId);
  } catch (error) {
    if (!onRefreshError) throw error;
    onRefreshError(error);
  }
  return response;
}
