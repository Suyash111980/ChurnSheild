import { apiRequest } from "./apiClient";
export const getLearners = (params = {}) => apiRequest(`/learners?${new URLSearchParams(params)}`);
export const getLearner = (learnerId) => apiRequest(`/learners/${encodeURIComponent(learnerId)}`);
