import test from "node:test";
import assert from "node:assert/strict";
import {
  adminRequestCount,
  adminRequestDisplayName,
  adminRequestError,
  adminRequestReviewerName,
  adminRequestStatusLabel,
  normalizeAdminRequestPage,
} from "../src/utils/adminRequestPresentation.js";

const validPage = {
  data: [{ id: "internal-id", display_name: "Anika Patel", email: "anika@example.test", status: "pending", created_at: "2026-10-20T10:00:00Z" }],
  counts: { pending: 1, approved: 2, rejected: 3 },
  count: 1, total: 6, limit: 20, offset: 0, has_more: false, activity: [],
};

test("request presentation uses actual name then email, never UUID", () => {
  assert.equal(adminRequestDisplayName({ display_name: "Anika Patel", email: "anika@example.test" }), "Anika Patel");
  assert.equal(adminRequestDisplayName({ display_name: "d272bc49-22fe-4eaf-a416-3cf48834fcd1", email: "anika@example.test" }), "anika@example.test");
  assert.equal(adminRequestDisplayName({ display_name: "d272bc49-22fe-4eaf-a416-3cf48834fcd1" }), "Unknown user");
});

test("reviewer presentation replaces unresolved placeholder names with a clear fallback", () => {
  assert.equal(adminRequestReviewerName({ reviewer_name: "Morgan Lee" }), "Morgan Lee");
  assert.equal(adminRequestReviewerName({ reviewer_name: "Unknown user" }), "Reviewer information unavailable");
  assert.equal(adminRequestReviewerName({ reviewer_name: null }), "Reviewer information unavailable");
});

test("request response validation preserves real counts and rejects malformed data", () => {
  assert.deepEqual(normalizeAdminRequestPage(validPage), validPage);
  assert.equal(normalizeAdminRequestPage({ ...validPage, counts: { ...validPage.counts, pending: "1" } }), null);
  assert.equal(normalizeAdminRequestPage({ ...validPage, data: [{ ...validPage.data[0], status: "denied" }] }), null);
});

test("request counts distinguish loading, errors, and real counts", () => {
  assert.equal(adminRequestCount(validPage.counts, "pending", { loading: true }), "…");
  assert.equal(adminRequestCount(validPage.counts, "pending", { error: true }), "Unavailable");
  assert.equal(adminRequestCount(validPage.counts, "approved"), 2);
});

test("status labels present the API request status vocabulary", () => {
  assert.equal(adminRequestStatusLabel("pending"), "Pending");
  assert.equal(adminRequestStatusLabel("approved"), "Approved");
  assert.equal(adminRequestStatusLabel("rejected"), "Rejected");
});

test("permanent route and authorization failures do not offer retry loops", () => {
  const missingRoute = adminRequestError({ status: 404 });
  assert.equal(missingRoute.retryable, false);
  assert.match(missingRoute.message, /restart FastAPI/i);
  assert.equal(adminRequestError({ status: 403 }).retryable, false);
  assert.equal(adminRequestError({ status: 503 }).retryable, true);
});
