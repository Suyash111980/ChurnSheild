export function createDatasetService(request) {
  return {
    uploadDataset: (formData) => request("/datasets/upload", { method: "POST", body: formData }),
    listDatasets: (params = {}) => {
      const query = new URLSearchParams({ limit: "100", offset: "0", ...params });
      return request(`/datasets?${query}`);
    },
    previewDataset: (formData) => request("/datasets/preview", { method: "POST", body: formData }),
    getDataset: (id) => request(`/datasets/${encodeURIComponent(id)}`),
    retryDataset: (id, formData) => request(`/datasets/${encodeURIComponent(id)}/retry`, { method: "POST", body: formData }),
    reprocessDataset: (id, formData) => request(`/datasets/${encodeURIComponent(id)}/reprocess`, { method: "POST", body: formData }),
  };
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
