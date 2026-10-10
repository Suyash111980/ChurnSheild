import { apiRequest } from "./apiClient";
export const getDashboardSummary = () => apiRequest("/dashboard/summary");
