// OPTION 4: SPLIT SCREEN DESIGN
// Modern split-screen layout with visual on one side, content on other

import React, { useState, useEffect } from "react";
import { useApiClient } from "../utils/apiClient";
import { useNavigate } from "react-router-dom";
import { useAuthSetup } from "../hooks/useAuthSetup";
import { AuthGuard } from "../components/AuthGuard";
import StravaConnectButton from "../components/StravaConnectButton";
import StravaAttribution from "../components/StravaAttribution";
import StravaConsentModal from "../components/StravaConsentModal";

const SetupPage: React.FC = () => {
  const api = useApiClient();
  const navigate = useNavigate();
  const { isReady, userId } = useAuthSetup();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [pendingStep, setPendingStep] = useState<1 | 2 | 3 | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [forceSyncing, setForceSyncing] = useState(false);
  const [hasStrava, setHasStrava] = useState(false);
  const [showConsentModal, setShowConsentModal] = useState(false);

  useEffect(() => {
    if (isReady && userId) {
      api.get<{ hasOnboarded: boolean; hasStrava: boolean }>("/user")
        .then((res) => {
          const { hasOnboarded, hasStrava: userHasStrava } = res.data;
          setHasStrava(userHasStrava);
          if (hasOnboarded) {
            setStep(3);
          } else if (userHasStrava) {
            setStep(2);
          } else {
            setStep(1);
          }
        })
        .catch((err) => console.error("❌ Failed to fetch user status:", err));
    }
  }, [isReady, userId, api]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("strava") === "connected") {
      setForceSyncing(true);
      setTimeout(() => {
        setForceSyncing(false);
        params.delete("strava");
        window.history.replaceState({}, "", `${window.location.pathname}`);
        if (isReady && userId) {
          api.get<{ hasOnboarded: boolean; hasStrava: boolean }>("/user")
            .then((res) => {
              const { hasOnboarded, hasStrava: userHasStrava } = res.data;
              setHasStrava(userHasStrava);
              if (hasOnboarded) {
                setStep(3);
              } else if (userHasStrava) {
                setStep(2);
              } else {
                setStep(1);
              }
            })
            .catch((err) => console.error("❌ Failed to refresh user status:", err));
        }
        if (pendingStep !== null) {
          setStep(pendingStep);
          setPendingStep(null);
        }
      }, 8000);
    }
  }, [pendingStep, isReady, userId, api]);

  const handleConnectClick = (e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
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
    const consentTimestamp = new Date().toISOString();
    console.log("✅ User consent granted at:", consentTimestamp);
    localStorage.setItem('strava_consent_timestamp', consentTimestamp);
    window.location.href = `${apiBase}/auth/strava-login?user_id=${encodeURIComponent(userId)}`;
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-white">
        <div className="grid md:grid-cols-2 min-h-screen">
          {/* Left Side - Visual/Illustration */}
          {/* Mobile: Compact header, Desktop: Full height side panel */}
          <div className="bg-gradient-to-br from-blue-600 via-blue-700 to-purple-700 flex items-center justify-center p-6 md:p-12 md:min-h-screen">
            <div className="text-center text-white w-full">
              {/* Mobile: Smaller icon and text, Desktop: Larger */}
              <div className="w-20 h-20 md:w-32 md:h-32 bg-white bg-opacity-20 rounded-full flex items-center justify-center mx-auto mb-4 md:mb-8">
                <svg className="w-10 h-10 md:w-16 md:h-16 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h2 className="text-2xl md:text-4xl font-bold mb-2 md:mb-4">Train Smarter</h2>
              <p className="text-base md:text-xl text-blue-100 px-4">
                Personalized plans that adapt to you
              </p>
            </div>
          </div>

          {/* Right Side - Content */}
          <div className="flex items-center justify-center p-6 md:p-12">
            <div className="max-w-md w-full">
              <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-2 md:mb-3">
                Welcome to SmartCoach
              </h1>
              <p className="text-lg md:text-xl text-gray-600 mb-6 md:mb-8">
                Your running training coach
              </p>

              {/* Features */}
              <div className="space-y-4 md:space-y-6 mb-8 md:mb-10">
                <div className="flex items-start gap-3 md:gap-4">
                  <div className="w-10 h-10 md:w-12 md:h-12 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0">
                    <svg className="w-5 h-5 md:w-6 md:h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1 text-sm md:text-base">Adaptive Plans</h3>
                    <p className="text-gray-600 text-xs md:text-sm">
                      Daily training plans that adjust to your progress
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 md:gap-4">
                  <div className="w-10 h-10 md:w-12 md:h-12 bg-purple-100 rounded-xl flex items-center justify-center flex-shrink-0">
                    <svg className="w-5 h-5 md:w-6 md:h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1 text-sm md:text-base">AI Coach</h3>
                    <p className="text-gray-600 text-xs md:text-sm">
                      Chat with an AI that knows your training history
                    </p>
                  </div>
                </div>
              </div>

              {/* CTA */}
              <div className="bg-gray-50 rounded-2xl p-5 md:p-6 border border-gray-200">
                <h3 className="font-semibold text-gray-900 mb-2 md:mb-3 text-base md:text-lg">Get Started</h3>
                <p className="text-xs md:text-sm text-gray-600 mb-4">
                  Connect your Strava account to sync your activities and create your plan
                </p>
                <StravaConnectButton
                  onClick={handleConnectClick}
                  disabled={!userId || syncing || forceSyncing}
                />
                <StravaAttribution className="mt-4" />
                {hasStrava && !syncing && !forceSyncing && (
                  <div className="mt-4 text-center">
                    <button
                      onClick={() => navigate("/onboarding")}
                      className="text-blue-600 hover:text-blue-700 font-medium"
                    >
                      Step 2: Complete Your Profile →
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {showConsentModal && (
          <StravaConsentModal
            onAccept={handleConsentAccept}
            onDecline={handleConsentDecline}
          />
        )}
      </div>
    </AuthGuard>
  );
};

export default SetupPage;
