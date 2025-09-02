// src/utils/apiClient.ts
import axios from "axios";
import { useAuth0 } from "@auth0/auth0-react";

export function useApiClient() {
  const { getAccessTokenSilently, loginWithRedirect } = useAuth0();

  const client = axios.create({ baseURL: "/api" });

  client.interceptors.request.use(async (config) => {
    try {
      const token = await getAccessTokenSilently({
        detailedResponse: false,
        // audience and scope are already configured in AuthProvider, so no need to repeat
      });

      if (token) {
        (config.headers ??= {});
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
      return config;
    } catch (err: any) {
      // No refresh token / consent not granted / third-party cookies blocked
      const msg = String(err?.error || err?.message || "");
      const needsConsent =
        msg.includes("missing_refresh_token") ||
        msg.includes("consent_required") ||
        msg.includes("login_required");

      if (needsConsent) {
        // Force a one-time re-consent to obtain a refresh token
        await loginWithRedirect({
          authorizationParams: {
            prompt: "consent", // ask again so we get offline_access
          },
          appState: { returnTo: window.location.pathname || "/dashboard" },
        });
      }

      throw err;
    }
  });

  return client;
}
