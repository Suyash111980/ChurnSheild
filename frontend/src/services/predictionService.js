import { apiRequest } from "./apiClient";

const queryString = (params) => new URLSearchParams(
  Object.entries(params).filter(([, value]) => value != null && value !== ""),
).toString();

export const listPredictions = (params = {}) =>
  apiRequest(`/predictions?${queryString(params)}`);

export const getPrediction = (predictionId, datasetId) =>
  apiRequest(`/predictions/${encodeURIComponent(predictionId)}?dataset_id=${encodeURIComponent(datasetId)}`);

export const getPredictionExplanations = (predictionId, datasetId) =>
  apiRequest(`/predictions/${encodeURIComponent(predictionId)}/explanations?dataset_id=${encodeURIComponent(datasetId)}`);

export const listLearnerPredictions = (learnerId, params = {}) =>
  apiRequest(`/learners/${encodeURIComponent(learnerId)}/predictions?${queryString(params)}`);
