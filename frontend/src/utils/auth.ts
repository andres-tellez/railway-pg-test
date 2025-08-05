// src/utils/auth.ts

export function getAccessToken(): string | null {
  return localStorage.getItem("access_token");
}

export function getAuthHeader(): { Authorization: string } | {} {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}


export function getUserIdFromToken(token: string): string | null {
  try {
    const base64 = token.split(".")[1];
    const decoded = JSON.parse(atob(base64));
    return decoded.sub;
  } catch (e) {
    console.error("❌ Failed to decode JWT:", e);
    return null;
  }
}
