// src/pages/PostOAuth.tsx
import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";

const API = import.meta.env.VITE_API_URL ?? "";

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

    const go = async () => {
      try {
        // 1) Create/refresh our identity on the API (protected)
        const token = await getAccessTokenSilently({
          authorizationParams: {
            audience: import.meta.env.VITE_AUTH0_AUDIENCE,
            scope: "openid profile email offline_access",
          },
        });

        // optional: keep using /api/user/identity ping if you want, but it’s not required.
        await fetch(`${API}/api/me`, {
          credentials: "include",
          headers: { Authorization: `Bearer ${token}` },
          signal: ac.signal,
        }).catch(() => {});

        // 2) Onboarding check (server uses token sub; no user_id param)
        const profRes = await fetch(`${API}/api/onboarding`, {
          credentials: "include",
          headers: { Authorization: `Bearer ${token}` },
          signal: ac.signal,
        });

        const ct = profRes.headers.get("content-type") || "";
        if (!ct.includes("application/json")) {
          throw new Error("onboarding returned non-JSON");
        }

        done = true;
        clearTimeout(safety);

        if (profRes.status === 404) {
          navigate("/onboarding", { replace: true });
        } else if (profRes.ok) {
          navigate("/dashboard", { replace: true });
        } else {
          throw new Error(`onboarding failed: ${profRes.status}`);
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
