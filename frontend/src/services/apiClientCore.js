export class ApiRequestError extends Error {
  constructor(status, detail = null) {
    super(`API request failed (${status})`);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

export function createApiClient({ supabase, baseUrl, fetchImpl = fetch }) {
  async function currentAccessToken() {
    const { data, error } = await supabase.auth.getSession();
    if (error) throw error;
    return data.session?.access_token ?? null;
  }

  function requestHeaders(options, accessToken) {
    const headers = new Headers(options.headers || {});
    const isFormData =
      typeof FormData !== "undefined" && options.body instanceof FormData;

    if (options.body != null && !isFormData && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    return headers;
  }

  async function apiFetch(path, options = {}) {
    const token = await currentAccessToken();
    const url = path.startsWith("http") ? path : `${baseUrl}${path}`;
    const send = (accessToken) =>
      fetchImpl(url, { ...options, headers: requestHeaders(options, accessToken) });

    let response = await send(token);
    if (response.status === 401 && token) {
      const { data, error } = await supabase.auth.refreshSession();
      const refreshedToken = data.session?.access_token;
      if (!error && refreshedToken && refreshedToken !== token) {
        response = await send(refreshedToken);
      }
    }
    return response;
  }

  async function apiRequest(path, options = {}) {
    const response = await apiFetch(path, options);
    if (!response.ok) {
      let detail = null;
      try {
        const body = await response.clone().json();
        if (typeof body?.detail === "string") detail = body.detail.slice(0, 240);
      } catch {
        // Keep the HTTP status when the response is not JSON.
      }
      throw new ApiRequestError(response.status, detail);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  return { apiFetch, apiRequest };
}
