// src/utils/apiClient.ts
import axios from "axios";
import { useAuth0 } from "@auth0/auth0-react";
import { useMemo } from "react";

import { getAuth0RedirectUri } from "@/auth/auth0RedirectUri";

export function useApiClient() {
  const { getAccessTokenSilently, loginWithRedirect } = useAuth0();

  // Rely on explicit backend URL (no automatic `/api` suffix to avoid double-prefix bugs)
  const rawBase = import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "") ?? "";
  const baseURL = rawBase || "";

  if (import.meta.env.MODE !== "production") {
    console.log("API baseURL =", baseURL);
  }

  // ✅ Use useMemo to create a stable axios instance
  const client = useMemo(() => {
    const axiosInstance = axios.create({
      baseURL,
      withCredentials: true, // ✅ This sends session cookies
    });

    // 🔑 Always attach access token
    axiosInstance.interceptors.request.use(async (config) => {
      try {
        const token = await getAccessTokenSilently({ detailedResponse: false });
        if (token) {
          (config.headers ??= {});
          (config.headers as any).Authorization = `Bearer ${token}`;
          console.log("🔑 API Request - Authorization header attached:", config.url);
        } else {
          console.warn("⚠️ API Request - No token available:", config.url);
        }
        return config;
      } catch (err: any) {
        const msg = String(err?.error || err?.message || "").toLowerCase();
        const needsConsent =
          msg.includes("missing_refresh_token") ||
          msg.includes("consent_required") ||
          msg.includes("login_required") ||
          msg.includes("invalid refresh token") ||
          msg.includes("invalid_refresh_token") ||
          msg.includes("unknown or invalid refresh token");

        if (needsConsent) {
          // Clear invalid tokens from localStorage before redirecting
          console.warn("⚠️ Invalid refresh token detected. Clearing auth cache and redirecting to login.");
          // Clear Auth0 cache keys from localStorage
          Object.keys(localStorage).forEach((key) => {
            if (key.startsWith("@@auth0spa@@")) {
              localStorage.removeItem(key);
            }
          });

          await loginWithRedirect({
            authorizationParams: {
              prompt: "login",
              redirect_uri: getAuth0RedirectUri(),
              audience: import.meta.env.VITE_AUTH0_AUDIENCE,
              scope: "openid profile email offline_access",
            },
            appState: { returnTo: window.location.pathname || "/dashboard" },
          });
          return config; // Prevent the request from continuing
        }
        throw err;
      }
    });

    // 🔑 Capture `user_id` from backend identity response
    axiosInstance.interceptors.response.use(
      (response) => {
        if (response.config.url?.includes("/user/identity")) {
          // Backend returns {data: {user_id: "..."}, status: 200}
          const userId = response.data.data?.user_id || response.data.user_id;
          if (userId) {
            localStorage.setItem("user_id", userId);
            if (import.meta.env.MODE !== "production") {
              console.log("✅ Stored internal user_id:", userId);
            }
          }
        }
        return response;
      },
      (error) => Promise.reject(error)
    );

    return axiosInstance;
  }, [baseURL, getAccessTokenSilently, loginWithRedirect]);

  return client;
}
