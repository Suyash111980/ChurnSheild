import { apiRequest } from "./apiClient";

export const getLearners = (params = {}, options = {}) => {
  const query = new URLSearchParams(params);
  return apiRequest(`/learners?${query}`, options);
};

export const getLearner = (learnerId, datasetId, options = {}) =>
  apiRequest(`/learners/${encodeURIComponent(learnerId)}?dataset_id=${encodeURIComponent(datasetId)}`, options);
