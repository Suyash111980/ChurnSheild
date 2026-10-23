import { apiRequest } from "./apiClient";
import { datasetScopeQuery } from "../utils/datasetScope";
export const getDashboardSummary = (datasetId) => apiRequest(`/dashboard/summary?${datasetScopeQuery(datasetId)}`);
export const getCourseInsights = (datasetId) => apiRequest(`/courses/insights?${datasetScopeQuery(datasetId)}`);
