import React, { useState, useEffect, useRef } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "../utils/apiClient";
import { useNavigate } from "react-router-dom";
import { useAuthSetup } from "../hooks/useAuthSetup";
import StravaConnectButton from "../components/StravaConnectButton";
import StravaAttribution from "../components/StravaAttribution";
import StravaConsentModal from "../components/StravaConsentModal";

const SetupPage: React.FC = () => {
  const { user } = useAuth0();
  const api = useApiClient();
  const navigate = useNavigate();
  const { isReady, userId, error: authError } = useAuthSetup();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [pendingStep, setPendingStep] = useState<1 | 2 | 3 | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [forceSyncing, setForceSyncing] = useState(false);

  // Consent modal state
  const [showConsentModal, setShowConsentModal] = useState(false);

  useEffect(() => {
    if (isReady && userId) {
      api.get<{ hasOnboarded: boolean; hasStrava: boolean }>("/user")
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
  }, [isReady, userId, api]); // Use the centralized auth setup

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

  const handleConnectClick = () => {
    // Show consent modal instead of directly connecting
    setShowConsentModal(true);
  };

  const handleConsentAccept = () => {
    setShowConsentModal(false);
    connectStrava();
  };

  const handleConsentDecline = () => {
    setShowConsentModal(false);
  };

  const connectStrava = () => {
    if (!userId) {
      console.error("❌ Cannot connect Strava: no internal userId yet");
      return;
    }

    const apiBase = import.meta.env.VITE_BACKEND_URL;
    setSyncing(true);

    // Log consent timestamp (you can also send this to backend)
    const consentTimestamp = new Date().toISOString();
    console.log("✅ User consent granted at:", consentTimestamp);
    localStorage.setItem('strava_consent_timestamp', consentTimestamp);

    window.location.href = `${apiBase}/auth/strava-login?user_id=${encodeURIComponent(
      userId
    )}`;
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
            <div className="mt-4 flex flex-col items-center">
              <StravaConnectButton
                onClick={handleConnectClick}
                disabled={!userId || syncing || forceSyncing}
              />
              <StravaAttribution className="mt-2" />
              <p className="text-sm text-gray-600 mt-1 text-center">
                {userId
                  ? step === 1
                    ? "Connect your Strava account to get started"
                    : "Reconnect or sync Strava data"
                  : "Waiting for identity…"}
              </p>
            </div>
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


      </div>
    </div>


    {/* Strava Consent Modal */}
    {showConsentModal && (
      <StravaConsentModal
        onAccept={handleConsentAccept}
        onDecline={handleConsentDecline}
      />
    )}
    </>
  );
};

export default SetupPage;
