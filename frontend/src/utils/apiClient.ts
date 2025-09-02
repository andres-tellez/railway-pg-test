// src/utils/apiClient.ts
import axios from "axios";
import { useAuth0 } from "@auth0/auth0-react";

export function useApiClient() {
  const { getAccessTokenSilently } = useAuth0();

  const client = axios.create({
    baseURL: "/api",
  });

  client.interceptors.request.use(
    async (config) => {
      const token = await getAccessTokenSilently();
      if (token) {
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  return client;
}
