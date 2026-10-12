import { supabase } from "../lib/supabase";
import { createApiClient } from "./apiClientCore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

const client = createApiClient({ supabase, baseUrl: API_BASE_URL });

export const { apiFetch, apiRequest } = client;
