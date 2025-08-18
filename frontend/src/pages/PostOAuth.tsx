// src/pages/PostOAuth.tsx
import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { authFetchJSON } from "../utils/authFetch";

const PostOAuth: React.FC = () => {
  const navigate = useNavigate();
  const { isLoading, isAuthenticated, getAccessTokenSilently } = useAuth0();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    if (isLoading || !isAuthenticated) return;
    ran.current = true;

    const ac = new AbortController();
    let done = false;

    const safety = setTimeout(() => {
      if (!done) navigate("/dashboard", { replace: true });
    }, 6000);

    const getToken = () =>
      getAccessTokenSilently({
        authorizationParams: {
          audience: import.meta.env.VITE_AUTH0_AUDIENCE,
          scope: "openid profile email offline_access",
        },
      });

    const go = async () => {
      try {
        // 1) Ensure user identity exists on the API (protected)
        // NOTE: backend route is "/me" (no "/api" prefix)
        try {
          await authFetchJSON("/me", getToken, { signal: ac.signal });
        } catch {
          // Non-blocking: identity helper failure shouldn't stop flow
        }

        // 2) Onboarding check (server uses token.sub; no user_id param)
        const { res } = await authFetchJSON("/api/onboarding", getToken, {
          signal: ac.signal,
        });

        done = true;
        clearTimeout(safety);

        if (res.status === 404) {
          navigate("/onboarding", { replace: true });
        } else if (res.ok) {
          navigate("/dashboard", { replace: true });
        } else {
          throw new Error(`onboarding failed with status ${res.status}`);
        }
      } catch {
        done = true;
        clearTimeout(safety);
        navigate("/onboarding", { replace: true });
      }
    };

    void go();
    return () => {
      clearTimeout(safety);
      ac.abort();
    };
  }, [isLoading, isAuthenticated, getAccessTokenSilently, navigate]);

  return <div>🔐 Finishing sign-in…</div>;
};

export default PostOAuth;
