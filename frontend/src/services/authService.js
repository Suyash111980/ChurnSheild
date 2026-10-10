import { apiRequest } from "./apiClient";
export const login = (credentials) => apiRequest("/auth/login", { method: "POST", body: JSON.stringify(credentials) });

