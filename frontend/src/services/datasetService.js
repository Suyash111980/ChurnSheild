import { apiRequest } from "./apiClient.js";
import { createDatasetService } from "./datasetServiceCore.js";

const service = createDatasetService(apiRequest);
export const { uploadDataset, listDatasets, previewDataset, getDataset, retryDataset, reprocessDataset } = service;
