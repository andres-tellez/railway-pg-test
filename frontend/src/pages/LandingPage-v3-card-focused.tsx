// OPTION 3: CARD-FOCUSED WITH STRONG VISUALS
// Large feature cards with illustrations and bold colors

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
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-5xl mx-auto px-4 py-12">
          {/* Header */}
          <div className="text-center mb-16">
            <h1 className="text-4xl md:text-5xl font-extrabold text-gray-900 mb-4">
              Welcome to SmartCoach
            </h1>
            <p className="text-xl text-gray-600">
              Your running training coach
            </p>
          </div>

          {/* Large Feature Cards */}
          <div className="grid md:grid-cols-2 gap-8 mb-12">
            {/* Feature Card 1 */}
            <div className="relative overflow-hidden bg-gradient-to-br from-blue-500 to-blue-600 rounded-3xl p-8 text-white shadow-2xl transform hover:scale-105 transition-transform">
              <div className="absolute top-0 right-0 w-32 h-32 bg-white opacity-10 rounded-full -mr-16 -mt-16"></div>
              <div className="relative z-10">
                <div className="w-20 h-20 bg-white bg-opacity-20 rounded-2xl flex items-center justify-center mb-6">
                  <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h3 className="text-2xl font-bold mb-3">Adaptive Plans</h3>
                <p className="text-blue-50 text-lg leading-relaxed">
                  Daily training plans that evolve with your progress
                </p>
              </div>
            </div>

            {/* Feature Card 2 */}
            <div className="relative overflow-hidden bg-gradient-to-br from-purple-500 to-purple-600 rounded-3xl p-8 text-white shadow-2xl transform hover:scale-105 transition-transform">
              <div className="absolute top-0 right-0 w-32 h-32 bg-white opacity-10 rounded-full -mr-16 -mt-16"></div>
              <div className="relative z-10">
                <div className="w-20 h-20 bg-white bg-opacity-20 rounded-2xl flex items-center justify-center mb-6">
                  <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <h3 className="text-2xl font-bold mb-3">AI Coach</h3>
                <p className="text-purple-50 text-lg leading-relaxed">
                  Chat with an AI that knows your complete training history
                </p>
              </div>
            </div>
          </div>

          {/* CTA Card */}
          <div className="bg-white rounded-3xl shadow-xl border-2 border-gray-100 p-10 max-w-2xl mx-auto">
            <div className="text-center">
              <h2 className="text-3xl font-bold text-gray-900 mb-4">Ready to Start Training?</h2>
              <p className="text-gray-600 mb-8 text-lg">
                Connect Strava to sync your running activities and create your personalized plan
              </p>
              <StravaConnectButton
                onClick={handleConnectClick}
                disabled={!userId || syncing || forceSyncing}
              />
              <StravaAttribution className="mt-4" />
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
