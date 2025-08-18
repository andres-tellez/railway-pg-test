// src/pages/PostOAuth.tsx
import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";

const API = import.meta.env.VITE_API_URL!; // e.g. https://api.smartcoach.dev

export default function PostOAuth() {
  const navigate = useNavigate();
  const { isLoading, isAuthenticated, getAccessTokenSilently } = useAuth0();

  useEffect(() => {
    if (isLoading || !isAuthenticated) return;

    (async () => {
      try {
        const token = await getAccessTokenSilently({
          authorizationParams: {
            audience: import.meta.env.VITE_AUTH0_AUDIENCE,
            scope: "openid profile email",
          },
        });

        // This call both verifies the token and ensures the user_identity row exists.
        await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
          credentials: "include",
        });
      } catch (e) {
        // If this fails, it should not block the UX.
        // We’re authenticated on the SPA either way.
        console.warn("auth/me failed:", e);
      } finally {
        navigate("/dashboard", { replace: true });
      }
    })();
  }, [isLoading, isAuthenticated, getAccessTokenSilently, navigate]);

  return <div>🔐 Finishing sign-in…</div>;
}
