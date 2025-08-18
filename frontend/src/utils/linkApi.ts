// src/utils/linkApi.ts
export type LinkStatus = { linked: boolean; user_id?: string; athlete_id?: number };

const API = import.meta.env.VITE_API_URL ?? "";

function safeJson<T = any>(res: Response): Promise<T> {
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    return res.text().then((t) => {
      const snippet = t.slice(0, 120);
      throw new Error(`Expected JSON, got ${res.status} ${res.statusText}. Body: ${snippet}`);
    });
  }
  return res.json();
}

export async function getLink(token: string): Promise<LinkStatus> {
  const res = await fetch(`${API}/api/user/link`, {
    method: "GET",
    headers: token && token !== "dev" ? { Authorization: `Bearer ${token}` } : {},
    credentials: "include",
  });
  if (res.status === 404) return { linked: false };
  const data = await safeJson(res);
  return { linked: true, user_id: data.user_id, athlete_id: data.athlete_id };
}

export async function postLink(token: string, athleteId: number): Promise<void> {
  const res = await fetch(`${API}/api/user/link`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token && token !== "dev" ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "include",
    body: JSON.stringify({ athlete_id: athleteId }),
  });
  await safeJson(res);
}

export async function deleteLink(token: string): Promise<void> {
  const res = await fetch(`${API}/api/user/link`, {
    method: "DELETE",
    headers: token && token !== "dev" ? { Authorization: `Bearer ${token}` } : {},
    credentials: "include",
  });
  await safeJson(res);
}
