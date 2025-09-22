import React, { useState, useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "../utils/apiClient";
import { LandingProgress } from "../components/LandingProgress";

const LandingPage: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth0();
  const api = useApiClient();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [syncing, setSyncing] = useState(false);
  const [userId, setUserId] = useState<string | null>(null); // ✅ UUID from backend

  // ✅ Always check backend for progress on load (via authenticated JWT)
  useEffect(() => {
    if (isAuthenticated && userId) {
      api
        .get("/progress/status")
        .then((res) => {
          const data = res.data;
          console.log("📥 Progress response:", data);

          if (data.stage === "done") {
            setStep(2);
            setSyncing(false);
          } else if (data.stage !== "starting") {
            setSyncing(true);
          } else {
            setSyncing(false);
          }
        })
        .catch((err) => {
          console.error("❌ Failed to check progress", err);
        });
    }
  }, [isAuthenticated, api, userId]);

  // ✅ Persist user identity once authenticated (and fetch UUID)
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      api
        .post<{ user_id: string }>("/user/identity")
        .then((res) => {
          console.log("✅ Stored internal user_id:", res.data.user_id);
          setUserId(res.data.user_id);
        })
        .catch((err) =>
          console.error("❌ Failed to upsert identity:", err)
        );
    }
  }, [isAuthenticated, isLoading, api]);

  // ✅ Correct connectStrava (only one copy)
  const connectStrava = () => {
    if (!userId) {
      console.error("❌ Cannot connect Strava: no internal userId yet");
      return;
    }
    const apiBase = import.meta.env.VITE_BACKEND_URL;

    setSyncing(true); // 🔑 Start showing progress UI when user clicks
    window.location.href = `${apiBase}/auth/strava-login?user_id=${encodeURIComponent(userId)}`;
  };

  if (isLoading) return <div className="p-6">🔄 Loading auth…</div>;
  if (!isAuthenticated)
    return <div className="p-6 text-red-600">❌ Not authenticated</div>;

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
            step === 1
              ? "bg-blue-50 border-blue-400 cursor-pointer"
              : "bg-gray-100 opacity-50"
          } ${!userId ? "opacity-50 cursor-not-allowed" : ""}`} // 🚫 disabled if no UUID yet
          onClick={() => {
            if (step === 1 && userId) {
              connectStrava();
            }
          }}
        >
          <h2 className="font-medium text-lg">Step 1: Connect Strava</h2>
          {syncing ? (
            <div className="mt-4">
              {userId && <LandingProgress userId={userId} />} {/* ✅ pass UUID */}
            </div>
          ) : (
            <p className="text-sm text-gray-600 mt-1">
              {userId
                ? "Click to connect your Strava account"
                : "Waiting for identity…"} {/* 🕒 clearer UX */}
            </p>
          )}
        </div>

        {/* Step 2 */}
        <div
          className={`p-4 border rounded-lg ${
            step >= 2
              ? "bg-blue-50 border-blue-400 cursor-pointer"
              : "bg-gray-100 opacity-50"
          }`}
          onClick={() => {
            console.log("🖱️ Step 2 clicked manually");
            if (step >= 2) {
              // Only navigate when the user clicks
              window.location.href = "/onboarding";
            }
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
            step >= 3
              ? "bg-blue-50 border-blue-400 cursor-pointer"
              : "bg-gray-100 opacity-50"
          }`}
          onClick={() => step >= 3 && (window.location.href = "/plan")}
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
