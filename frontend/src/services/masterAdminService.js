import { apiRequest } from "./apiClient";

/** Master Admin-only aggregate metadata from the existing backend contract. */
export function getMasterAdminOverview() {
  return apiRequest("/master-admin/overview");
}
