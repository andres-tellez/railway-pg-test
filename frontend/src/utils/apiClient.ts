// src/utils/apiClient.ts
import axios from "axios";
import { useAuth0 } from "@auth0/auth0-react";

export function useApiClient() {
  const { getAccessTokenSilently, isAuthenticated, isLoading } = useAuth0();

  const call = async (method: string, url: string, data?: any, config?: any) => {
    if (isLoading) return; // 🛑 Wait until Auth0 finishes
    if (!isAuthenticated) throw new Error("Not authenticated");

    const token = await getAccessTokenSilently({
      authorizationParams: {
        audience: import.meta.env.VITE_AUTH0_AUDIENCE,
      },
    });

    return axios({
      method,
      url: `${import.meta.env.VITE_API_BASE_URL}${url}`,
      data,
      headers: {
        Authorization: `Bearer ${token}`,
        ...config?.headers,
      },
      ...config,
    });
  };

  return { call };
}
