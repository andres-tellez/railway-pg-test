// src/pages/PostOAuth.tsx
import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { postLink } from "../utils/linkApi";

const API = import.meta.env.VITE_API_URL ?? "";

const PostOAuth: React.FC = () => {
  const navigate = useNavigate();
  const { isLoading, isAuthenticated, user, getAccessTokenSilently } = useAuth0();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    if (isLoading || !isAuthenticated || !user?.sub) return;
    ran.current = true;

    const ac = new AbortController();
    let done = false;

    const safety = setTimeout(() => {
      if (!done) navigate("/dashboard", { replace: true });
    }, 6000);

    const go = async () => {
      try {
        console.groupCollapsed("[PostOAuth] handoff");
        console.log("user.sub:", user.sub);

        // 1) Persist Auth0 identity
        try {
          const identityRes = await fetch(`${API}/api/user/identity`, {
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

          console.log("identity status:", identityRes.status);
        } catch (err) {
          console.warn("⚠️ identity POST failed:", err);
        }

        // 2) whoami + link attempt
        try {
          const token = await getAccessTokenSilently({
            authorizationParams: {
              audience: import.meta.env.VITE_AUTH0_AUDIENCE,
              scope: "openid profile email offline_access",
            },
          }).catch(() => "dev");

          const whoRes = await fetch(`${API}/auth/whoami`, {
            credentials: "include",
            headers: { Authorization: `Bearer ${token}` },
            signal: ac.signal,
          });

          const text = await whoRes.text();
          if (!whoRes.ok || !whoRes.headers.get("content-type")?.includes("application/json")) {
            console.warn("⚠️ whoami failed or returned HTML:", whoRes.status, text.slice(0, 100));
          } else {
            try {
              const { strava_athlete_id: athlete_id } = JSON.parse(text);
              if (typeof athlete_id === "number") {
                
                try {
                  await postLink(token, athlete_id);
                  console.log("✅ Link created successfully");
                } catch (err) {
                  console.error("❌ Failed to link user to athlete", err);
                }

                console.log("link: attempted");
              }
            } catch (err) {
              console.warn("⚠️ whoami JSON parse failed:", err);
            }
          }
        } catch (err) {
          console.warn("⚠️ whoami/link request failed:", err);
        }

        // 3) Onboarding check
        try {
          const profRes = await fetch(
            `${API}/api/onboarding?user_id=${encodeURIComponent(user.sub)}`,
            { credentials: "include", signal: ac.signal }
          );

          const contentType = profRes.headers.get("content-type") ?? "";
          if (!contentType.includes("application/json")) {
            throw new Error("onboarding returned HTML or invalid response");
          }

          done = true;
          clearTimeout(safety);

          if (profRes.status === 404) {
            navigate("/onboarding", { replace: true });
          } else if (profRes.ok) {
            navigate("/dashboard", { replace: true });
          } else {
            throw new Error(`onboarding failed with status ${profRes.status}`);
          }
        } catch (err) {
          console.error("⚠️ onboarding check failed:", err);
          done = true;
          clearTimeout(safety);
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
