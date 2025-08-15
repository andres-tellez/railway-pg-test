// src/hooks/useAuthSync.ts
import { useAuth0 } from "@auth0/auth0-react";
import { useEffect, useMemo, useState } from "react";

export function useAuthSync(): string | null {
  const { isLoading, isAuthenticated, user } = useAuth0();
  const [id, setId] = useState<string | null>(null);

  // 1) Try URL ?user_id= first (nice for deep-links)
  const urlUserId = useMemo(() => {
    try {
      return new URLSearchParams(window.location.search).get("user_id");
    } catch {
      return null;
    }
  }, []);

  // Prime from URL/localStorage once
  useEffect(() => {
    if (urlUserId) {
      localStorage.setItem("user_id", urlUserId);
      setId(urlUserId);
      console.debug("[AuthSync] using user_id from URL:", urlUserId);
      return;
    }
    const cached = localStorage.getItem("user_id");
    if (cached) {
      setId(cached);
      console.debug("[AuthSync] using user_id from localStorage:", cached);
    }
  }, [urlUserId]);

  // 2) When Auth0 is ready, prefer user.sub
  useEffect(() => {
    if (isLoading) return;
    if (isAuthenticated && user?.sub) {
      if (id !== user.sub) {
        localStorage.setItem("user_id", user.sub);
        setId(user.sub);
        console.debug("[AuthSync] using user_id from Auth0:", user.sub);
      }
    }
  }, [isLoading, isAuthenticated, user, id]);

  return id;
}
