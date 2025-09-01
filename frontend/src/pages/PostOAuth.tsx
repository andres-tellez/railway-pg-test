import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";

const PostOAuth: React.FC = () => {
  const navigate = useNavigate();
  const { isLoading, isAuthenticated, getAccessTokenSilently } = useAuth0();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current || isLoading || !isAuthenticated) return;
    ran.current = true;

    const ac = new AbortController();
    let done = false;

    const safety = setTimeout(() => {
      if (!done) navigate("/dashboard", { replace: true });
    }, 6000);

    const go = async () => {
      try {
        const token = await getAccessTokenSilently({
          authorizationParams: {
            audience: import.meta.env.VITE_AUTH0_AUDIENCE,
            scope: "openid profile email offline_access",
          },
        });

        // 1. Save user identity
        await fetch("/api/user/identity", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({}),
          signal: ac.signal,
        });

        // 2. Ensure user is created
        await fetch("/api/user", {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          signal: ac.signal,
        });

        // 3. Check onboarding status
        const onboardingRes = await fetch("/api/onboarding", {
          headers: { Authorization: `Bearer ${token}` },
          signal: ac.signal,
        });

        done = true;
        clearTimeout(safety);

        if (onboardingRes.status === 404) {
          navigate("/onboarding", { replace: true });
        } else if (onboardingRes.ok) {
          navigate("/dashboard", { replace: true });
        } else {
          throw new Error(`Unexpected response: ${onboardingRes.status}`);
        }
      } catch (err) {
        console.error("PostOAuth error:", err);
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
