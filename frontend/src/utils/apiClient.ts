// src/utils/apiClient.ts
import axios from "axios";
import { useAuth0 } from "@auth0/auth0-react";
import { useMemo } from "react";

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
    // Ensure absolute URLs have /api in the pathname
    if (!url.pathname.endsWith("/api") && url.pathname !== "/api") {
      url.pathname = url.pathname.replace(/\/$/, "") + "/api";
    }
    base = url.toString().replace(/\/$/, "");
  }

  const baseURL = base;

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
