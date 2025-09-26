import React, { useState, useEffect, useRef } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "../utils/apiClient";
import { useNavigate } from "react-router-dom";

const LandingPage: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth0();
  const api = useApiClient();
  const navigate = useNavigate();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [syncing, setSyncing] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);

  const hasPostedIdentity = useRef(false);

  // ✅ Initial identity sync + fetch user status
  useEffect(() => {
    if (isAuthenticated && !isLoading && !hasPostedIdentity.current) {
      hasPostedIdentity.current = true;

      api
        .post<{ user_id: string }>("/user/identity")   // 🔧 removed `/api`
        .then((res) => {
          const newUserId = res.data.user_id;
          setUserId(newUserId);

          return api.get<{ hasOnboarded: boolean; hasStrava: boolean }>("/user"); // 🔧 removed `/api`
        })
        .then((res) => {
          const { hasOnboarded, hasStrava } = res.data;
          console.log("📊 User status:", res.data);

          if (hasOnboarded) {
            setStep(3);
          } else if (hasStrava) {
            setStep(2);
          } else {
            setStep(1);
          }
        })
        .catch((err) => console.error("❌ Failed to fetch user status:", err));
    }
  }, [isAuthenticated, isLoading, api]);

  // ✅ Detect Strava redirect success
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("strava") === "connected") {
      console.log("🔄 Strava connected, starting sync spinner");
      setSyncing(true);

      params.delete("strava");
      window.history.replaceState({}, "", `${window.location.pathname}`);

      // ⚠️ better: poll /user, but temporary timeout is okay
      setTimeout(() => {
        setSyncing(false);
        console.log("⏱ Done syncing. Awaiting status re-evaluation.");
      }, 8000);
    }
  }, []);

  // ✅ Detect onboarding redirect (optional)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("onboarding") === "done") {
      console.log("✅ Onboarding finished. Clearing param only.");
      params.delete("onboarding");
      window.history.replaceState({}, "", `${window.location.pathname}`);
    }
  }, []);

  const connectStrava = () => {
    if (!userId) {
      console.error("❌ Cannot connect Strava: no internal userId yet");
      return;
    }

    const apiBase = import.meta.env.VITE_BACKEND_URL;
    setSyncing(true);

    window.location.href = `${apiBase}/auth/strava-login?user_id=${encodeURIComponent(
      userId
    )}`;
  };

  if (isLoading) return <div className="p-6">🔄 Loading auth…</div>;
  if (!isAuthenticated) return <div className="p-6 text-red-600">❌ Not authenticated</div>;

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 bg-gray-50">
      {/* Profile */}
      <div className="flex items-center gap-4 mt-8 mb-6">
        {user?.picture ? (
          <img
            src={user.picture}
            alt={user.name || "User"}
            className="w-12 h-12 rounded-full border border-gray-300"
          />
        ) : (
          <div className="w-12 h-12 rounded-full bg-gray-300" />
        )}
        <h1 className="text-2xl font-semibold text-gray-900">
          {user?.name || "Runner"}
        </h1>
      </div>

      {/* Steps */}
      <div className="w-full max-w-md space-y-6">
        {/* Step 1 */}
        <div
          className={`p-4 border rounded-lg ${
            step === 1 ? "bg-blue-50 border-blue-400 cursor-pointer" : "bg-gray-100 opacity-50"
          } ${!userId ? "opacity-50 cursor-not-allowed" : ""}`}
          onClick={() => {
            if (step === 1 && userId && !syncing) {
              connectStrava();
            }
          }}
        >
          <h2 className="font-medium text-lg">Step 1: Connect Strava</h2>
          {syncing ? (
            <div className="mt-4 flex flex-col items-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="text-sm text-gray-600 mt-2">Syncing your Strava data…</p>
            </div>
          ) : (
            <p className="text-sm text-gray-600 mt-1">
              {userId ? "Click to connect your Strava account" : "Waiting for identity…"}
            </p>
          )}
        </div>

        {/* Step 2 */}
        <div
          className={`p-4 border rounded-lg ${
            step === 2 ? "bg-blue-50 border-blue-400 cursor-pointer" : "bg-gray-100 opacity-50"
          }`}
          onClick={() => {
            if (step === 2) navigate("/onboarding");
          }}
        >
          <h2 className="font-medium text-lg">Step 2: Complete Onboarding</h2>
          <p className="text-sm text-gray-600 mt-1">
            Answer a few quick questions about your goals
          </p>
        </div>

        {/* Step 3 */}
        <div
          className={`p-4 border rounded-lg ${
            step === 3 ? "bg-blue-50 border-blue-400 cursor-pointer" : "bg-gray-100 opacity-50"
          }`}
          onClick={() => {
            if (step === 3) navigate("/plan");
          }}
        >
          <h2 className="font-medium text-lg">Step 3: Generate Plan</h2>
          <p className="text-sm text-gray-600 mt-1">
            Build your personalized running plan
          </p>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;
