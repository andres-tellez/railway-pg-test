// frontend/src/utils/linkApi.ts
export type LinkStatus = {
  linked: boolean;
  user_id?: string;
  athlete_id?: number;
};

export async function getLink(token: string): Promise<LinkStatus> {
  const res = await fetch("/api/user/link", {
    headers: { Authorization: `Bearer ${token}` },
    credentials: "include",
  });
  if (res.status === 404) return { linked: false };
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function postLink(token: string, athlete_id: number): Promise<LinkStatus> {
  const res = await fetch("/api/user/link", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    credentials: "include",
    body: JSON.stringify({ athlete_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteLink(token: string): Promise<{ deleted: boolean }> {
  const res = await fetch("/api/user/link", {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
    credentials: "include",
  });
  if (res.status === 404) return { deleted: false };
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
