// src/pages/PostOAuth.tsx
import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "@/utils/apiClient";

const PostOAuth: React.FC = () => {
  const navigate = useNavigate();
  const { isLoading, isAuthenticated } = useAuth0();
  const ran = useRef(false);
  const api = useApiClient();

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
        // 1. Save user identity
        await api.post("/api/user/identity", {}, { signal: ac.signal });

        // 2. Ensure user is created
        await api.get("/api/user", { signal: ac.signal });

        // 3. Check onboarding status
        const res = await api.get("/api/onboarding", { signal: ac.signal });

        done = true;
        clearTimeout(safety);

        if (res.status === 404) {
          navigate("/onboarding", { replace: true });
        } else if (res.status === 200) {
          navigate("/dashboard", { replace: true });
        } else {
          throw new Error(`Unexpected response: ${res.status}`);
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
  }, [isLoading, isAuthenticated, api, navigate]);

  return <div>🔐 Finishing sign-in…</div>;
};

export default PostOAuth;
