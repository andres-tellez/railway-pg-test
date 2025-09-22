// src/pages/PostOAuth.tsx
import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "@/utils/apiClient";

const PostOAuth: React.FC = () => {
  const navigate = useNavigate();
  const { isLoading, isAuthenticated, getIdTokenClaims } = useAuth0();
  const api = useApiClient();
  const ran = useRef(false);

  useEffect(() => {
    console.log("🔍 PostOAuth mounted →", { isLoading, isAuthenticated });

    if (ran.current) return;
    if (isLoading) {
      console.log("⏳ Auth0 still loading, skipping");
      return;
    }

    if (!isAuthenticated) {
      console.warn("🚨 Not authenticated after loading → sending to /login");
      navigate("/login", { replace: true });
      return;
    }

    ran.current = true;

    const ac = new AbortController();
    let done = false;

    // Fallback safety (prevents user being stuck forever)
    const safety = setTimeout(() => {
      if (!done) navigate("/", { replace: true }); // ✅ fallback to LandingPage
    }, 8000);

    const go = async () => {
      try {
        const claims = await getIdTokenClaims();
        const idToken = claims?.__raw;
        console.log("🪪 ID token →", idToken ? "present" : "missing");

        if (!idToken) throw new Error("No Auth0 id_token found");

        const base = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000";
        console.log("📡 Posting token to backend:", base);

        const resp = await fetch(`${base}/auth/login/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: idToken }),
          credentials: "include",
          signal: ac.signal,
        });

        console.log("📡 /auth/login/callback →", resp.status);

        if (!resp.ok) {
          const body = await resp.text().catch(() => "");
          throw new Error(`auth/login/callback failed: ${resp.status} ${body}`);
        }

        // ✅ Fixed: no double `/api`
        await api.post("/user/identity", {}, { signal: ac.signal });
        await api.get("/user", { signal: ac.signal });

        done = true;
        clearTimeout(safety);

        // ✅ Always go back to LandingPage.
        navigate("/", { replace: true });
      } catch (err) {
        console.error("❌ PostOAuth error:", err);
        done = true;
        clearTimeout(safety);
        navigate("/", { replace: true });
      }
    };

    void go();

    return () => {
      clearTimeout(safety);
      ac.abort();
    };
  }, [isLoading, isAuthenticated, getIdTokenClaims, api, navigate]);

  return <div className="p-6">🔐 Finishing sign-in…</div>;
};

export default PostOAuth;
