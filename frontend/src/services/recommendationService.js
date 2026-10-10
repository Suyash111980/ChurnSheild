import { apiRequest } from "./apiClient";
export const getRecommendations = (params = {}) => apiRequest(`/recommendations?${new URLSearchParams(params)}`);
export const updateRecommendation = (id, payload) => apiRequest(`/recommendations/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) });
