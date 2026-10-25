import { apiRequest } from "./apiClient";

export function getAdminRequests({ status, search, dateFrom, dateTo, sort, limit, offset }) {
  const query = new URLSearchParams({ status, sort, limit: String(limit), offset: String(offset) });
  if (search.trim()) query.set("search", search.trim());
  if (dateFrom) query.set("date_from", dateFrom);
  if (dateTo) query.set("date_to", dateTo);
  return apiRequest(`/admin/requests?${query.toString()}`);
}

export function getAdminRequestDetails(requestId) {
  return apiRequest(`/admin/requests/${encodeURIComponent(requestId)}/details`);
}

export function reviewAdminRequest(requestId, decision, rejectionReason = "") {
  return apiRequest(`/admin/users/${encodeURIComponent(requestId)}/approval`, {
    method: "PATCH",
    body: JSON.stringify({ decision, rejection_reason: rejectionReason || null }),
  });
}
