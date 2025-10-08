import React, { useState, useEffect, useRef } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "../utils/apiClient";
import { useNavigate } from "react-router-dom";
import SafetyWarningModal from "../components/SafetyWarningModal";

const SetupPage: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth0();
  const api = useApiClient();
  const navigate = useNavigate();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [pendingStep, setPendingStep] = useState<1 | 2 | 3 | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [forceSyncing, setForceSyncing] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);

  // Safety warning modal state
  const [showSafetyModal, setShowSafetyModal] = useState(false);
  const [safetyMessage, setSafetyMessage] = useState('');

  const hasPostedIdentity = useRef(false);

  useEffect(() => {
    if (
      isAuthenticated &&
      !isLoading &&
      !hasPostedIdentity.current &&
      !syncing &&
      !forceSyncing
    ) {
      hasPostedIdentity.current = true;

      api
        .post<{ user_id: string }>("/user/identity")
        .then((res) => {
          const newUserId = res.data.user_id;
          setUserId(newUserId);

          return api.get<{ hasOnboarded: boolean; hasStrava: boolean }>("/user");
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
        .catch((err) =>
          console.error("❌ Failed to fetch user status:", err)
        );
    }
  }, [isAuthenticated, isLoading, syncing, forceSyncing]); // Remove 'api' to prevent infinite loop

  // ✅ Detect Strava redirect success
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("strava") === "connected") {
      console.log("🔄 Strava connected, forcing sync spinner");
      setForceSyncing(true);

      setTimeout(() => {
        setForceSyncing(false);
        console.log("⏱ Done syncing. Awaiting status re-evaluation.");
        params.delete("strava");
        window.history.replaceState({}, "", `${window.location.pathname}`);

        if (pendingStep !== null) {
          setStep(pendingStep);
          setPendingStep(null);
        }
      }, 8000);
    }
  }, [pendingStep]);

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

  const generatePlan = async () => {
  if (!userId) {
    console.error("❌ Cannot generate plan: no internal userId yet");
    return;
  }

  try {
    console.log("📡 Sending generatePlan request...");

    const res = await api.post<{ plan_id: number }>("/api/plan/generate", {
      user_id: userId,
      // Race data will come from user_profile table
    });

    const planId = res.data.plan_id;
    console.log("✅ Generated plan, navigating to:", `/plan/${planId}`);

    //navigate(`/plan/${planId}`); // ⬅️ should redirect now
    navigate('/plan/overview');
    console.log("➡️ navigate() called!");
  } catch (err: any) {
    console.error("❌ Failed to generate plan:", err);
    if (err.response?.data?.error) {
      const errorData = err.response.data;
      // Check if this is a safety-related error
      if (errorData.safety_blocked) {
        setSafetyMessage(errorData.error);
        setShowSafetyModal(true);
      } else {
        alert(errorData.error);
      }
    } else {
      alert('Failed to generate training plan. Please try again.');
    }
  }
};


  if (isLoading) return <div className="p-6">🔄 Loading auth…</div>;
  if (!isAuthenticated)
    return <div className="p-6 text-red-600">❌ Not authenticated</div>;

  return (
    <>
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Welcome to SmartCoach
        </h1>
        <p className="text-gray-600">
          Let's get you set up with your personalized training plan
        </p>
      </div>

      {/* Steps */}
      <div className="w-full max-w-md space-y-6 mx-auto">
        {/* Step 1 */}
        <div
          className={`p-4 border rounded-lg ${
            step === 1 || (step === 2 && !syncing && !forceSyncing)
              ? "bg-blue-50 border-blue-400 cursor-pointer"
              : "bg-gray-100 opacity-50"
          } ${!userId ? "opacity-50 cursor-not-allowed" : ""}`}
          onClick={() => {
            if ((step === 1 || step === 2) && userId && !syncing && !forceSyncing) {
              connectStrava();
            }
          }}
        >
          <h2 className="font-medium text-lg">Step 1: Connect Strava</h2>
          {(syncing || forceSyncing) ? (
            <div className="mt-4 flex flex-col items-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="text-sm text-gray-600 mt-2">
                Syncing your Strava data…
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-600 mt-1">
              {userId
                ? step === 1
                  ? "Click to connect your Strava account"
                  : "Click to reconnect or sync Strava data"
                : "Waiting for identity…"}
            </p>
          )}
        </div>

        {/* Step 2 */}
        <div
          className={`p-4 border rounded-lg ${
            step === 2
              ? "bg-blue-50 border-blue-400 cursor-pointer"
              : "bg-gray-100 opacity-50"
          }`}
          onClick={() => {
            if (step === 2 && !forceSyncing) navigate("/onboarding");
          }}
        >
          <h2 className="font-medium text-lg">Step 2: Complete Onboarding</h2>
          {forceSyncing ? (
            <div className="mt-4 flex flex-col items-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="text-sm text-gray-600 mt-2">
                Syncing your Strava data…
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-600 mt-1">
              Answer a few quick questions about your goals
            </p>
          )}
        </div>
        {/* Step 3 */}
        <div
          className={`p-4 border rounded-lg ${
            step === 3
              ? "bg-blue-50 border-blue-400 cursor-pointer"
              : "bg-gray-100 opacity-50"
          }`}
          onClick={() => {
            if (step === 3 && !forceSyncing && userId) {
              generatePlan(); // ⬅️ use the function
            }
          }}
        >
          <h2 className="font-medium text-lg">Step 3: Generate Plan</h2>
          {forceSyncing ? (
            <div className="mt-4 flex flex-col items-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="text-sm text-gray-600 mt-2">
                Syncing your Strava data…
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-600 mt-1">
              Build your personalized running plan
            </p>
          )}
        </div>


      </div>
    </div>

    {/* Safety Warning Modal */}
    <SafetyWarningModal
      isOpen={showSafetyModal}
      onClose={() => setShowSafetyModal(false)}
      message={safetyMessage}
    />
    </>
  );
};

export default SetupPage;
