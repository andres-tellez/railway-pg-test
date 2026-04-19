// src/utils/apiClient.ts
import axios from "axios";
import { useAuth0 } from "@auth0/auth0-react";
import { useMemo } from "react";

import { getAuth0RedirectUri } from "@/auth/auth0RedirectUri";
import { createAuthRedirectError, needsReauthentication } from "@/utils/authRenewal";

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
      } catch (err: unknown) {
        if (needsReauthentication(err)) {
          console.warn(
            "⚠️ Session cannot be refreshed. Clearing Auth0 cache and redirecting to login.",
            err,
          );
          Object.keys(localStorage).forEach((key) => {
            if (key.startsWith("@@auth0spa@@")) {
              localStorage.removeItem(key);
            }
          });

          void loginWithRedirect({
            authorizationParams: {
              prompt: "login",
              redirect_uri: getAuth0RedirectUri(),
              audience: import.meta.env.VITE_AUTH0_AUDIENCE,
              scope: "openid profile email offline_access",
            },
            appState: {
              returnTo: `${window.location.pathname}${window.location.search}`,
            },
          });
          /* Do not send API calls without Bearer — page should navigate to Auth0 */
          return Promise.reject(createAuthRedirectError());
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
