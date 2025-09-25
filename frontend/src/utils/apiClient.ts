// src/utils/apiClient.ts
import axios from "axios";
import { useAuth0 } from "@auth0/auth0-react";

export function useApiClient() {
  const { getAccessTokenSilently, loginWithRedirect } = useAuth0();

  // ✅ Use only VITE_BACKEND_URL (must be set in Railway + .env.local)
  let base = import.meta.env.VITE_BACKEND_URL || "/api";

  // Normalize: remove trailing slash
  if (base.endsWith("/")) base = base.slice(0, -1);

  // If absolute (https://api.smartcoach.dev), ensure it ends with `/api`
  const isAbsolute = /^https?:\/\//i.test(base);
  if (isAbsolute) {
    const url = new URL(base);
    //if (!url.pathname.endsWith("/api")) {
    //  url.pathname = url.pathname.replace(/\/$/, "") + "/api";
    //}
    base = url.toString().replace(/\/$/, "");
  }

  const baseURL = base;

  if (import.meta.env.MODE !== "production") {
    console.log("API baseURL =", baseURL);
  }

  const client = axios.create({ baseURL });

  // 🔑 Always attach access token
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

  // 🔑 Capture `user_id` from backend identity response
  client.interceptors.response.use(
    (response) => {
      if (
        response.config.url?.includes("/user/identity") &&
        response.data?.user_id
      ) {
        localStorage.setItem("user_id", response.data.user_id);
        if (import.meta.env.MODE !== "production") {
          console.log("✅ Stored internal user_id:", response.data.user_id);
        }
      }
      return response;
    },
    (error) => Promise.reject(error)
  );

  return client;
}
