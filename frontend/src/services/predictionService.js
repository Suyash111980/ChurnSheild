import { apiRequest } from "./apiClient";
export const createPredictions = (payload) => apiRequest("/predictions", { method: "POST", body: JSON.stringify(payload) });
