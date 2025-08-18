// src/utils/authFetch.ts
const API = import.meta.env.VITE_API_URL ?? "";

/**
 * Fetches an API path with an Auth0 Bearer token and returns parsed JSON.
 * Throws a readable error if the server responds with non-JSON (e.g. HTML 401 page).
 */
export async function authFetchJSON(
  path: string,
  getToken: () => Promise<string>,
  init: RequestInit = {}
) {
  const token = await getToken();

  const res = await fetch(`${API}${path}`, {
    credentials: "include", // keep, so Strava session cookies still flow when needed
    ...init,
    headers: {
      ...(init.headers || {}),
      Authorization: `Bearer ${token}`,
      // keep content-type when POSTing JSON; don't force it for GETs
      ...(init.method && init.method !== "GET"
        ? { "Content-Type": "application/json" }
        : {}),
    },
  });

  const contentType = res.headers.get("content-type") || "";
  const text = await res.text();

  if (!contentType.includes("application/json")) {
    throw new Error(
      `HTTP ${res.status} — expected JSON, got: ${text.slice(0, 160)}`
    );
  }

  const json = JSON.parse(text);
  return { res, json };
}

/** Convenience for POSTing JSON bodies. */
export function postJSON(
  path: string,
  body: unknown,
  getToken: () => Promise<string>,
  init: RequestInit = {}
) {
  return authFetchJSON(
    path,
    getToken,
    { method: "POST", body: JSON.stringify(body), ...init }
  );
}
