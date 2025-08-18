// src/utils/linkApi.ts
import { authFetchJSON } from "./authFetch";

export type LinkStatus =
  | { linked: false }
  | { linked: true; user_id: string; athlete_id: number };

export async function getLink(getToken: () => Promise<string>) {
  const { json } = await authFetchJSON<LinkStatus>("/api/user/link", getToken);
  return json;
}

export async function postLink(getToken: () => Promise<string>, athlete_id: number) {
  const { json } = await authFetchJSON<LinkStatus>("/api/user/link", getToken, {
    method: "POST",
    body: JSON.stringify({ athlete_id }),
  });
  return json;
}

export async function deleteLink(getToken: () => Promise<string>) {
  await authFetchJSON("/api/user/link", getToken, { method: "DELETE" });
  return true;
}
