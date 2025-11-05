// OPTION 1: BOLD HERO WITH GRADIENT
// Modern, eye-catching design with gradient background and large icons

import React, { useState, useEffect, useRef } from "react";
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
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
        {/* Hero Section */}
        <div className="max-w-4xl mx-auto px-4 py-12">
          <div className="text-center mb-12">
            <h1 className="text-5xl font-bold text-gray-900 mb-4 bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-purple-600">
              Welcome to SmartCoach
            </h1>
            <p className="text-2xl text-gray-700 font-medium mb-2">
              Your running training coach
            </p>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Personalized daily training plans that adapt to your progress
            </p>
          </div>

          {/* Feature Cards - Large & Prominent */}
          <div className="grid md:grid-cols-2 gap-6 mb-12 max-w-3xl mx-auto">
            <div className="bg-white rounded-2xl p-8 shadow-xl border-2 border-blue-200 hover:shadow-2xl transition-all transform hover:-translate-y-1">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center mb-4 mx-auto">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2 text-center">Adaptive Plans</h3>
              <p className="text-gray-600 text-center leading-relaxed">
                Daily training plans that automatically adjust to your progress
              </p>
            </div>

            <div className="bg-white rounded-2xl p-8 shadow-xl border-2 border-purple-200 hover:shadow-2xl transition-all transform hover:-translate-y-1">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl flex items-center justify-center mb-4 mx-auto">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2 text-center">AI Coach</h3>
              <p className="text-gray-600 text-center leading-relaxed">
                Chat with an AI coach that knows your complete training history
              </p>
            </div>
          </div>

          {/* CTA Section */}
          <div className="max-w-2xl mx-auto bg-white rounded-3xl p-8 shadow-2xl border border-gray-100">
            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-3">Ready to Start?</h2>
              <p className="text-gray-600">
                Connect your Strava account to begin your personalized training journey
              </p>
            </div>

            {/* Step 1 - Integrated */}
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-2xl p-6 border-2 border-blue-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 text-center">Step 1: Connect Strava</h3>
              <div className="flex flex-col items-center">
                <StravaConnectButton
                  onClick={handleConnectClick}
                  disabled={!userId || syncing || forceSyncing}
                />
                <StravaAttribution className="mt-4" />
                <p className="text-sm text-gray-600 mt-4 text-center max-w-md">
                  We'll sync your running activities to understand your fitness level and keep your plan updated
                </p>
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
