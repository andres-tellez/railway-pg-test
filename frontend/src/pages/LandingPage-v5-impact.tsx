// OPTION 5: MAXIMUM IMPACT
// Bold, confident design with strong typography and visual elements

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
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-purple-900 text-white">
        {/* Animated Background Elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-20 left-20 w-72 h-72 bg-blue-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse"></div>
          <div className="absolute top-40 right-20 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse delay-1000"></div>
        </div>

        <div className="relative z-10 max-w-6xl mx-auto px-4 py-16">
          {/* Hero Section */}
          <div className="text-center mb-16">
            <div className="inline-block mb-6">
              <span className="text-6xl font-black bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400">
                SmartCoach
              </span>
            </div>
            <p className="text-2xl text-blue-200 font-light mb-4">
              Your AI-powered running coach
            </p>
            <p className="text-xl text-gray-300 max-w-2xl mx-auto">
              Get personalized daily training plans that adapt to your progress
            </p>
          </div>

          {/* Feature Showcase */}
          <div className="grid md:grid-cols-2 gap-8 mb-16 max-w-4xl mx-auto">
            <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-3xl p-8 border border-white border-opacity-20 hover:bg-opacity-20 transition-all">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-400 to-blue-600 rounded-2xl flex items-center justify-center mb-6">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold mb-3">Adaptive Training</h3>
              <p className="text-gray-300 leading-relaxed">
                Your plan evolves automatically as you train, adjusting to your performance and progress
              </p>
            </div>

            <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-3xl p-8 border border-white border-opacity-20 hover:bg-opacity-20 transition-all">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-400 to-purple-600 rounded-2xl flex items-center justify-center mb-6">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold mb-3">AI Coach</h3>
              <p className="text-gray-300 leading-relaxed">
                Ask anything about your training. Our AI coach knows your complete history and goals
              </p>
            </div>
          </div>

          {/* CTA Section */}
          <div className="max-w-2xl mx-auto text-center">
            <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-3xl p-10 border border-white border-opacity-20">
              <h2 className="text-3xl font-bold mb-4">Ready to Transform Your Training?</h2>
              <p className="text-gray-300 mb-8 text-lg">
                Connect Strava to sync your running activities and create your personalized training plan
              </p>
              <div className="transform hover:scale-105 transition-transform">
                <StravaConnectButton
                  onClick={handleConnectClick}
                  disabled={!userId || syncing || forceSyncing}
                />
              </div>
              <StravaAttribution className="mt-6 opacity-80" />
              {hasStrava && !syncing && !forceSyncing && (
                <div className="mt-6 text-center">
                  <button
                    onClick={() => navigate("/onboarding")}
                    className="text-white bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-medium"
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
