// @file PostOAuth.tsx
// @description: Handles Strava OAuth callback, token exchange, and ingestion trigger
// @features: Auth0 token processing, secure backend login, polling ingestion status
// @integration-points: Auth0, /auth/login/callback, /user/identity, LandingProgress
// @usage: Called via redirect after Strava OAuth completes
// @prerequisites: Auth0 must return valid id_token, user must be authenticated

import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "@/utils/apiClient";
import { LandingProgress } from "@/components/LandingProgress";

const PostOAuth: React.FC = () => {
  const navigate = useNavigate();
  const { isLoading, isAuthenticated, getIdTokenClaims, user } = useAuth0();
  const api = useApiClient();
  const ran = useRef(false);

  const [readyToSync, setReadyToSync] = useState(false);

  useEffect(() => {
    console.log("🔍 PostOAuth mounted →", { isLoading, isAuthenticated });

    if (isLoading) {
      console.log("⏳ Auth0 still loading, skipping");
      return;
    }

    if (!isAuthenticated) {
      console.warn("🚨 Not authenticated after loading → sending to /login");
      navigate("/login", { replace: true });
      return;
    }

    if (ran.current) return;
    ran.current = true;

    const ac = new AbortController();
    const safety = setTimeout(() => {
      console.warn("⏱️ Safety timeout triggered, redirecting");
      navigate("/", { replace: true });
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

        await api.post("/user/identity", {}, { signal: ac.signal });
        await api.get("/user", { signal: ac.signal });

        clearTimeout(safety);
        setReadyToSync(true); // ✅ Show LandingProgress now
      } catch (err) {
        console.error("❌ PostOAuth error:", err);
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

  if (readyToSync) {
    return (
      <LandingProgress
        userId={user?.sub || ""}
        onComplete={() => navigate("/", { replace: true })}
      />
    );
  }

  return <div className="p-6">🔐 Finishing sign-in…</div>;
};

export default PostOAuth;
