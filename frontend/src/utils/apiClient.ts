// src/utils/apiClient.ts
import axios from "axios";
import { useAuth0 } from "@auth0/auth0-react";

export function useApiClient() {
  const { getAccessTokenSilently, loginWithRedirect } = useAuth0();

  // Prefer VITE_API_BASE_URL, then VITE_API_URL, else fall back to relative '/api'
  let base = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "/api";

  // Normalize: remove trailing slash
  if (base.endsWith("/")) base = base.slice(0, -1);

  // If absolute (https://api.smartcoach.dev) ensure it ends with /api
  // If relative (/api), keep as-is
  const isAbsolute = /^https?:\/\//i.test(base);
  const baseURL = isAbsolute ? (base.endsWith("/api") ? base : `${base}/api`) : base;

  // (Optional) log in non-prod
  if (import.meta.env.MODE !== "production") {
    // eslint-disable-next-line no-console
    console.log("API baseURL =", baseURL);
  }

  const client = axios.create({ baseURL });

  client.interceptors.request.use(async (config) => {
    try {
      const token = await getAccessTokenSilently({ detailedResponse: false });
      if (token) {
        (config.headers ??= {});
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
      return config;
    } catch (err: any) {
      const msg = String(err?.error || err?.message || "");
      const needsConsent =
        msg.includes("missing_refresh_token") ||
        msg.includes("consent_required") ||
        msg.includes("login_required");

      if (needsConsent) {
        await loginWithRedirect({
          authorizationParams: { prompt: "consent" },
          appState: { returnTo: window.location.pathname || "/dashboard" },
        });
      }
      throw err;
    }
  });

  return client;
}
