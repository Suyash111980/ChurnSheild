import assert from "node:assert/strict";
import test from "node:test";
import { datasetStatusMessage, overviewErrorMessage, overviewMetricValue } from "../src/utils/masterAdminOverview.js";
import { ApiRequestError, createApiClient } from "../src/services/apiClientCore.js";

const supabase = { auth: { getSession: async () => ({ data: { session: null }, error: null }) } };

test("keeps real zero counts and represents empty database results as empty", () => {
  assert.equal(overviewMetricValue(0), 0);
  assert.equal(overviewMetricValue(undefined), "Unavailable");
  assert.equal(overviewMetricValue(undefined, { loading: true }), "Loading…");
  assert.equal(datasetStatusMessage({ dataset_status_counts: {} }), "No datasets recorded.");
});

test("maps auth, database, and network failures to distinct actionable messages", () => {
  assert.match(overviewErrorMessage({ status: 401 }), /Sign in again/);
  assert.match(overviewErrorMessage({ status: 403 }), /not authorized/);
  assert.match(overviewErrorMessage({ status: 503 }), /deployed database migrations/);
  assert.match(overviewErrorMessage(new TypeError("fetch failed")), /backend connection/);
  assert.equal(datasetStatusMessage(null, { error: true }), "Dataset status is unavailable because the platform overview request failed.");
});

test("API client preserves HTTP status for retryable platform error states", async () => {
  const client = createApiClient({
    supabase,
    baseUrl: "http://api.test/api/v1",
    fetchImpl: async () => new Response(JSON.stringify({ detail: "Safe database configuration hint." }), { status: 503 }),
  });
  await assert.rejects(client.apiRequest("/master-admin/overview"), (error) => {
    assert.ok(error instanceof ApiRequestError);
    assert.equal(error.status, 503);
    assert.equal(error.detail, "Safe database configuration hint.");
    return true;
  });
});
