import { apiRequest } from "./apiClient";
export const getRecommendations = (params = {}, options = {}) => apiRequest(`/recommendations?${new URLSearchParams(params)}`, options);
export const getEarlyWarnings = (params = {}) => apiRequest(`/early-warning?${new URLSearchParams(params)}`);
export const getModelEvaluation = () => apiRequest("/analytics/model-evaluation");
export const updateRecommendationForDataset = (id, datasetId, status) => apiRequest(`/recommendations/${encodeURIComponent(id)}?dataset_id=${encodeURIComponent(datasetId)}`, { method: "PATCH", body: JSON.stringify({ status }) });
