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
        } catch (err) {
          console.warn("identity: failed", err);
        }

        // 2) Try whoami + postLink
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

          console.log("whoami status:", whoRes.status);
          const contentType = whoRes.headers.get("content-type") ?? "";

          if (!whoRes.ok) {
            const text = await whoRes.text().catch(() => "unknown");
            console.warn(`⚠️ whoami failed: ${whoRes.status} - ${text}`);
          } else if (contentType.includes("application/json")) {
            const data = await whoRes.json().catch(err => {
              console.warn("⚠️ Failed to parse whoami JSON:", err);
              return {};
            });

            const athlete_id = data?.athlete_id;
            console.log("whoami athlete_id:", athlete_id);

            if (typeof athlete_id === "number") {
              await postLink(token, athlete_id).catch(err =>
                console.warn("linking failed", err)
              );
              console.log("link: attempted");
            }
          } else {
            const text = await whoRes.text().catch(() => "unknown");
            console.warn("⚠️ whoami returned non-JSON:", text);
          }
        } catch (err) {
          console.warn("whoami/link: error", err);
        }

        // 3) Fetch onboarding status and redirect
        try {
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
          console.warn("onboarding fetch failed", err);
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
