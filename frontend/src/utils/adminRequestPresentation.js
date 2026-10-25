const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function adminRequestDisplayName(request) {
  const name = typeof request?.display_name === "string" ? request.display_name.trim() : "";
  if (name && !UUID_PATTERN.test(name)) return name;
  const email = typeof request?.email === "string" ? request.email.trim() : "";
  return email || "Unknown user";
}

export function adminRequestReviewerName(request) {
  const name = typeof request?.reviewer_name === "string" ? request.reviewer_name.trim() : "";
  return name && name.toLowerCase() !== "unknown user" ? name : "Reviewer information unavailable";
}

export function normalizeAdminRequestPage(payload) {
  if (!payload || !Array.isArray(payload.data) || !payload.counts || !Array.isArray(payload.activity)) return null;
  const statuses = ["pending", "approved", "rejected"];
  if (statuses.some((status) => !Number.isInteger(payload.counts[status]) || payload.counts[status] < 0)) return null;
  if (!Number.isInteger(payload.count) || !Number.isInteger(payload.total) || !Number.isInteger(payload.limit) || !Number.isInteger(payload.offset) || typeof payload.has_more !== "boolean") return null;
  if (payload.data.some((request) => !request || !request.id || !statuses.includes(request.status) || !request.created_at)) return null;
  return payload;
}

export function adminRequestCount(counts, status, { loading = false, error = false } = {}) {
  if (error) return "Unavailable";
  if (loading) return "…";
  return Number.isInteger(counts?.[status]) ? counts[status] : "Unavailable";
}

export function adminRequestStatusLabel(status) {
  return ({ pending: "Pending", approved: "Approved", rejected: "Rejected" })[status] || "Unknown status";
}

export function adminRequestError(error) {
  if (error?.status === 404) {
    return {
      message: "This backend does not expose the Admin Requests API. Update or restart FastAPI, then confirm GET /api/v1/admin/requests appears in /docs.",
      retryable: false,
    };
  }
  if (error?.status === 401 || error?.status === 403) {
    return { message: "Your session is not authorized to manage Admin requests. Sign in with the configured Master Admin account.", retryable: false };
  }
  if (error?.status === 400 || error?.status === 422) {
    return { message: error.detail || "Check the request filters and try again.", retryable: false };
  }
  return {
    message: error?.detail || error?.message || "Admin requests could not be loaded. Retry in a moment.",
    retryable: true,
  };
}
