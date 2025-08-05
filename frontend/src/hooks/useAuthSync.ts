import { useEffect, useState } from "react";

export function useAuthSync() {
  const [token, setToken] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    const url = new URL(window.location.href);
    const urlToken = url.searchParams.get("access_token");
    const localToken = localStorage.getItem("access_token");

    console.log("🧩 URL Token from query:", urlToken);
    console.log("💾 Local storage token:", localToken);

    if (urlToken) {
      // Accept ANY token string, no JWT validation
      localStorage.setItem("access_token", urlToken);
      setToken(urlToken);
      console.log("✅ Token set from URL");
    } else if (localToken) {
      setToken(localToken);
      console.log("✅ Token set from localStorage");
    } else {
      setToken(null);
      console.warn("❌ No token found at all");
    }
  }, []);

  return token;
}
