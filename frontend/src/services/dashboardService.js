import { apiRequest } from "./apiClient";
import { datasetScopeQuery } from "../utils/datasetScope";
export const getDashboardSummary = (datasetId, options = {}) => apiRequest(`/dashboard/summary?${datasetScopeQuery(datasetId)}`, options);
export const getCourseInsights = (datasetId) => apiRequest(`/courses/insights?${datasetScopeQuery(datasetId)}`);
