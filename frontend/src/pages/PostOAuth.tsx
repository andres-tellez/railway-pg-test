// src/pages/PostOAuth.tsx
import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { postLink } from "../utils/linkApi";

const API = import.meta.env.VITE_API_URL ?? ""; // "" => Vite proxy in dev

const PostOAuth: React.FC = () => {
  const navigate = useNavigate();
  const { isLoading, isAuthenticated, user, getAccessTokenSilently } = useAuth0();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;                      // avoid double-run in StrictMode
    if (isLoading || !isAuthenticated || !user?.sub) return;
    ran.current = true;

    const ac = new AbortController();
    let done = false;

    // Safety: bail to dashboard if something stalls
    const safety = setTimeout(() => {
      if (!done) navigate("/dashboard", { replace: true });
    }, 6000);

    const go = async () => {
      try {
        console.groupCollapsed("[PostOAuth] handoff");
        console.log("user.sub:", user.sub);

        // 1) Persist Auth0 identity (non-blocking; safe to ignore failures)
        try {
          await fetch(`${API}/api/user/identity`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
              user_id: user.sub,
              email: user.email ?? null,
              email_verified: (user as any)?.email_verified ?? null,
              name: user.name ?? (user as any)?.nickname ?? null,
              picture: user.picture ?? null,
            }),
            signal: ac.signal,
          });
          console.log("identity: ok");
        } catch {
          console.log("identity: skipped/failed");
        }

        // 1.5) Auto-link user ↔ athlete from Strava session (non-blocking)
        try {
          const whoRes = await fetch(`${API}/auth/whoami`, {
            credentials: "include", // send Flask session cookie
            signal: ac.signal,
          });
          console.log("whoami status:", whoRes.status);
          if (whoRes.ok) {
            try {
              const { athlete_id } = (await whoRes.json()) as { athlete_id?: number };
              console.log("whoami athlete_id:", athlete_id);
              if (typeof athlete_id === "number") {
                const token = await getAccessTokenSilently({
                  authorizationParams: {
                    audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                    scope: "openid profile email offline_access",
                  },
                }).catch(() => "dev"); // local AUTH_BYPASS fallback
                await postLink(token, athlete_id).catch(() => {});
                console.log("link: attempted (201 or 409 expected)");
              }
            } catch (err) {
              console.warn("⚠️ whoami response was not valid JSON:", err);
            }
          } else {
            const text = await whoRes.text();
            console.warn(`⚠️ whoami failed: ${whoRes.status} - ${text}`);
          }
        } catch {
          console.log("whoami/link: skipped/failed");
        }

        // 2) Check onboarding profile and route appropriately
        const profRes = await fetch(
          `${API}/api/onboarding?user_id=${encodeURIComponent(user.sub)}`,
          { credentials: "include", signal: ac.signal }
        );
        console.log("onboarding status:", profRes.status);

        done = true;
        clearTimeout(safety);

        if (profRes.status === 404) {
          navigate("/onboarding", { replace: true });
        } else if (profRes.ok) {
          navigate("/dashboard", { replace: true });
        } else {
          navigate("/onboarding", { replace: true });
        }
      } catch (err) {
        if ((err as any)?.name !== "AbortError") {
          console.error("PostOAuth flow failed:", err);
          done = true;
          clearTimeout(safety);
          navigate("/onboarding", { replace: true });
        }
      } finally {
        console.groupEnd();
      }
    };

    void go();
    return () => {
      clearTimeout(safety);
      ac.abort();
    };
  }, [isLoading, isAuthenticated, user, getAccessTokenSilently, navigate]);

  return <div>🔐 Finishing sign-in…</div>;
};

export default PostOAuth;
