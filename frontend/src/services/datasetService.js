import { apiRequest } from "./apiClient.js";
import { createDatasetService } from "./datasetServiceCore.js";

const service = createDatasetService(apiRequest);
export const { uploadDataset, listDatasets, previewDataset, getDataset, deleteDataset, retryDataset, reprocessDataset } = service;
