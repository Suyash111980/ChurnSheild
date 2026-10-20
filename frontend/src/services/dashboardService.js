import { apiRequest } from "./apiClient";
export const getDashboardSummary = (datasetId) => apiRequest(`/dashboard/summary?dataset_id=${encodeURIComponent(datasetId)}`);
