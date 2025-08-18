// src/utils/apiClient.ts
import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { useAuth0 } from "@auth0/auth0-react";

export function useApiClient(): AxiosInstance {
  const { getAccessTokenSilently } = useAuth0();

  const client = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL as string,
    withCredentials: true, // 🔐 Send cookies
  });

  client.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
      const token = await getAccessTokenSilently({
        authorizationParams: {
          audience: import.meta.env.VITE_AUTH0_AUDIENCE as string,
        },
      });
      config.headers.Authorization = `Bearer ${token}`;
      return config;
    }
  );

  return client;
}
