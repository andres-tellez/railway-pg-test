// If you already use axios elsewhere, keep it; otherwise fetch works fine.
export async function getWhoAmI(apiBase: string, getToken: () => Promise<string>) {
  const token = await getToken();
  const res = await fetch(`${apiBase}/auth/whoami`, {
    method: 'GET',
    credentials: 'include',                // keep cookies (for future Strava session)
    headers: { Authorization: `Bearer ${token}` },
  });

  // Avoid the "Unexpected token '<'" parse error on non-200s
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`whoami ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}
