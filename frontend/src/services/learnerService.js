import { apiRequest } from "./apiClient";

export const getLearners = (params = {}, options = {}) => {
  const query = new URLSearchParams(Object.fromEntries(
    Object.entries(params).filter(([, value]) => value != null && value !== "")
  ));
  return apiRequest(`/learners?${query}`, options);
};

export const getLearner = (learnerId, datasetId, options = {}) =>
  apiRequest(`/learners/${encodeURIComponent(learnerId)}?dataset_id=${encodeURIComponent(datasetId)}`, options);
