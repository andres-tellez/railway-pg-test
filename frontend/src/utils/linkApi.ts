// src/utils/linkApi.ts
import { useApiClient } from "./apiClient";

export type LinkStatus =
  | { linked: false }
  | { linked: true; user_id: string; athlete_id: number };

export function useLinkApi() {
  const api = useApiClient();

  const getLink = async (): Promise<LinkStatus> => {
    const { data } = await api.get<LinkStatus>("/api/user/link");
    return data;
  };

  const postLink = async (athlete_id: number): Promise<LinkStatus> => {
    const { data } = await api.post<LinkStatus>("/api/user/link", { athlete_id });
    return data;
  };

  const deleteLink = async (): Promise<boolean> => {
    await api.delete("/api/user/link");
    return true;
  };

  return { getLink, postLink, deleteLink };
}
