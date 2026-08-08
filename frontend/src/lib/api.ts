import { supabase } from "./supabaseClient";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/** Every backend call goes through here so the Supabase access token is
 * always attached — the backend independently verifies it (see
 * backend/app/core/auth.py), it isn't trusted just because it's present. */
export async function apiFetch(path: string, options: RequestInit = {}) {
  const response = await apiFetchRaw(path, options);

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${response.status}`);
  }

  return response.json();
}

/** Same auth handling as `apiFetch`, but hands back the raw Response without
 * throwing on non-2xx. Needed for endpoints that return binary (the TTS route
 * returns MP3 bytes) and for callers that must inspect the status code —
 * /api/tts answers 503 to mean "degrade to the browser voice", which is a
 * normal outcome rather than an error to surface. */
export async function apiFetchRaw(path: string, options: RequestInit = {}): Promise<Response> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) throw new Error("Not authenticated");

  const isFormData = options.body instanceof FormData;

  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      Authorization: `Bearer ${session.access_token}`,
      ...options.headers,
    },
  });
}
