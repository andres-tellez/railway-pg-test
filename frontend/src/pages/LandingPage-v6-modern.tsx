// OPTION 6: MODERN & CLEAN
// Contemporary design with subtle animations and premium feel

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
        {/* Top accent bar */}
        <div className="h-2 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500"></div>

        <div className="max-w-4xl mx-auto px-6 py-20">
          {/* Header */}
          <div className="text-center mb-20">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-3xl mb-6 shadow-lg">
              <span className="text-white text-3xl font-bold">SC</span>
            </div>
            <h1 className="text-5xl md:text-6xl font-extrabold text-gray-900 mb-4">
              SmartCoach
            </h1>
            <p className="text-2xl text-gray-600 font-medium">
              Your running training coach
            </p>
          </div>

          {/* Feature Section */}
          <div className="mb-20">
            <div className="grid md:grid-cols-2 gap-8">
              <div className="group">
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-2xl p-8 border-2 border-blue-200 transition-all group-hover:shadow-xl group-hover:border-blue-300">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="w-14 h-14 bg-blue-500 rounded-xl flex items-center justify-center">
                      <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <h3 className="text-xl font-bold text-gray-900">Adaptive Plans</h3>
                  </div>
                  <p className="text-gray-700 leading-relaxed">
                    Daily training plans that automatically adjust to your progress and performance
                  </p>
                </div>
              </div>

              <div className="group">
                <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-2xl p-8 border-2 border-purple-200 transition-all group-hover:shadow-xl group-hover:border-purple-300">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="w-14 h-14 bg-purple-500 rounded-xl flex items-center justify-center">
                      <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>
                    </div>
                    <h3 className="text-xl font-bold text-gray-900">AI Coach</h3>
                  </div>
                  <p className="text-gray-700 leading-relaxed">
                    Get personalized answers from an AI coach that understands your complete training journey
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* CTA Section */}
          <div className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-3xl p-10 border border-gray-200">
            <div className="text-center max-w-2xl mx-auto">
              <h2 className="text-3xl font-bold text-gray-900 mb-3">
                Let's Get Started
              </h2>
              <p className="text-gray-600 mb-8 text-lg">
                Connect your Strava account to sync your running activities and create your personalized training plan
              </p>
              <div className="flex justify-center">
                <StravaConnectButton
                  onClick={handleConnectClick}
                  disabled={!userId || syncing || forceSyncing}
                />
              </div>
              <StravaAttribution className="mt-6" />
              {hasStrava && !syncing && !forceSyncing && (
                <div className="mt-6 text-center">
                  <button
                    onClick={() => navigate("/onboarding")}
                    className="text-gray-900 bg-white hover:bg-gray-50 px-6 py-3 rounded-lg font-medium border border-gray-300"
                  >
                    Step 2: Complete Your Profile →
                  </button>
                </div>
              )}
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
