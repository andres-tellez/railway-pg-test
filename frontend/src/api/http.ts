// src/api/http.ts
export async function getWhoAmI(apiBase: string, getToken: () => Promise<string>) {
  const token = await getToken();
  const res = await fetch(`${apiBase}/api/me`, {
    method: "GET",
    credentials: "include",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`me ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}
