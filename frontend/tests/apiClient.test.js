import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createApiClient } from "../src/services/apiClientCore.js";
import { createDatasetService } from "../src/services/datasetServiceCore.js";

function mockSupabase({ token = null, refreshedToken = null, refreshError = null } = {}) {
  const calls = { getSession: 0, refreshSession: 0, signOut: 0 };
  const supabase = {
    auth: {
      async getSession() {
        calls.getSession += 1;
        return { data: { session: token ? { access_token: token } : null }, error: null };
      },
      async refreshSession() {
        calls.refreshSession += 1;
        return {
          data: { session: refreshedToken ? { access_token: refreshedToken } : null },
          error: refreshError,
        };
      },
      async signOut() {
        calls.signOut += 1;
      },
    },
  };
  return { supabase, calls };
}

function response(status, body = "{}") {
  return new Response(body, { status, headers: { "Content-Type": "application/json" } });
}

describe("authenticated API client", () => {
  it("accepts a 204 No Content delete response without trying to parse JSON", async () => {
    const { supabase } = mockSupabase({ token: "delete-token" });
    const client = createApiClient({
      supabase,
      baseUrl: "http://api.test/v1",
      fetchImpl: async () => new Response(null, { status: 204 }),
    });
    const datasets = createDatasetService(client.apiRequest);

    assert.equal(await datasets.deleteDataset("dataset-1"), null);
  });

  it("attaches the current access token to backend requests", async () => {
    const { supabase } = mockSupabase({ token: "test-access-token" });
    let requestOptions;
    const client = createApiClient({
      supabase,
      baseUrl: "http://api.test/v1",
      fetchImpl: async (_url, options) => {
        requestOptions = options;
        return response(200);
      },
    });

    await client.apiFetch("/learners");

    assert.equal(requestOptions.headers.get("Authorization"), "Bearer test-access-token");
  });

  it("refreshes and retries once with a changed access token after 401", async () => {
    const { supabase, calls } = mockSupabase({
      token: "expired-token",
      refreshedToken: "new-token",
    });
    const sentTokens = [];
    const client = createApiClient({
      supabase,
      baseUrl: "http://api.test/v1",
      fetchImpl: async (_url, options) => {
        sentTokens.push(options.headers.get("Authorization"));
        return response(sentTokens.length === 1 ? 401 : 200);
      },
    });

    const result = await client.apiFetch("/learners");

    assert.equal(result.status, 200);
    assert.deepEqual(sentTokens, ["Bearer expired-token", "Bearer new-token"]);
    assert.equal(calls.refreshSession, 1);
  });

  it("does not retry more than once if the refreshed request also returns 401", async () => {
    const { supabase, calls } = mockSupabase({ token: "old", refreshedToken: "new" });
    let requestCount = 0;
    const client = createApiClient({
      supabase,
      baseUrl: "http://api.test/v1",
      fetchImpl: async () => {
        requestCount += 1;
        return response(401);
      },
    });

    const result = await client.apiFetch("/learners");

    assert.equal(result.status, 401);
    assert.equal(requestCount, 2);
    assert.equal(calls.refreshSession, 1);
  });

  it("does not retry when session refresh fails or returns no changed token", async () => {
    for (const refreshResult of [
      { token: "old", refreshedToken: null, refreshError: new Error("refresh failed") },
      { token: "old", refreshedToken: "old" },
    ]) {
      const { supabase, calls } = mockSupabase(refreshResult);
      let requestCount = 0;
      const client = createApiClient({
        supabase,
        baseUrl: "http://api.test/v1",
        fetchImpl: async () => {
          requestCount += 1;
          return response(401);
        },
      });

      assert.equal((await client.apiFetch("/learners")).status, 401);
      assert.equal(requestCount, 1);
      assert.equal(calls.refreshSession, 1);
    }
  });

  it("does not send an Authorization header without a Supabase session", async () => {
    const { supabase, calls } = mockSupabase();
    let requestOptions;
    const client = createApiClient({
      supabase,
      baseUrl: "http://api.test/v1",
      fetchImpl: async (_url, options) => {
        requestOptions = options;
        return response(200);
      },
    });

    await client.apiFetch("/health");

    assert.equal(requestOptions.headers.has("Authorization"), false);
    assert.equal(calls.refreshSession, 0);
  });

  it("preserves multipart content type handling for dataset uploads", async () => {
    const { supabase } = mockSupabase({ token: "upload-token" });
    let requestOptions;
    const client = createApiClient({
      supabase,
      baseUrl: "http://api.test/v1",
      fetchImpl: async (_url, options) => {
        requestOptions = options;
        return response(200);
      },
    });
    const form = new FormData();
    form.set("file", new Blob(["fixture"]), "fixture.csv");

    await client.apiFetch("/datasets/upload", { method: "POST", body: form });

    assert.equal(requestOptions.headers.get("Authorization"), "Bearer upload-token");
    assert.equal(requestOptions.headers.has("Content-Type"), false);
  });
});
