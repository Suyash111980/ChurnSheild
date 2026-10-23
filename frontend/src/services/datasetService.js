import { apiRequest } from "./apiClient.js";
import { createDatasetService } from "./datasetServiceCore.js";

const service = createDatasetService(apiRequest);
export const { uploadDataset, listDatasets, previewDataset, getDataset, retryDataset, reprocessDataset } = service;
export const deleteDataset = (datasetId, options = {}) => apiRequest(`/datasets/${encodeURIComponent(datasetId)}`, { ...options, method: "DELETE" });
