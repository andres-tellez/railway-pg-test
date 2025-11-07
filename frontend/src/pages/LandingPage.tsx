// Setup Page - Main onboarding page for connecting Strava and completing profile

import React, { useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { AuthGuard } from "../components/AuthGuard";
import { FeatureCard } from "../components/setup/FeatureCard";
import { StravaConnectSection } from "../components/setup/StravaConnectSection";
import { CalendarIcon, ChatIcon } from "../components/setup/FeatureIcons";
import StravaConsentModal from "../components/StravaConsentModal";
import { useStravaSetup } from "../hooks/useStravaSetup";

const SetupPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    isSyncing,
    isComplete,
    isLoading,
    error,
    userId,
    showConsentModal,
    handleConnectClick,
    handleConsentAccept,
    handleConsentDecline,
    retryFetch,
  } = useStravaSetup();

  // Memoize navigation callback to prevent recreation on every render
  const handleNavigateToOnboarding = useCallback(() => {
    navigate("/onboarding");
  }, [navigate]);

  // Memoize feature cards data to prevent recreation
  const featureCards = useMemo(() => [
    {
      icon: <CalendarIcon />,
      title: "Adaptive Plans",
      description: "Daily training plans that adjust to your progress",
      color: "blue" as const,
    },
    {
      icon: <ChatIcon />,
      title: "AI Coach",
      description: "Chat with an AI that knows your training history",
      color: "purple" as const,
    },
  ], []);

  return (
    <AuthGuard>
      <div className="min-h-screen bg-white">
        <div className="flex justify-center pt-4 md:pt-8 pb-8 px-6 md:px-12">
          <div className="max-w-md w-full">
            {/* Header */}
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-3 leading-tight">
              Welcome to SmartCoach
            </h1>
            <p className="text-lg md:text-xl text-gray-600 mb-8 md:mb-10 leading-relaxed">
              Your running training coach
            </p>

            {/* Feature Cards */}
            <div className="space-y-3 mb-6 md:mb-8">
              {featureCards.map((card) => (
                <FeatureCard
                  key={card.title}
                  icon={card.icon}
                  title={card.title}
                  description={card.description}
                  color={card.color}
                />
              ))}
            </div>

            {/* Transition Bridge */}
            <div className="text-center mb-6">
              <p className="text-base text-gray-600 font-medium mb-3">
                Ready to get started?
              </p>
              <div className="h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent max-w-xs mx-auto"></div>
            </div>

            {/* Step 1 Card */}
            <div className="bg-gray-50 rounded-lg p-5 md:p-6 border border-gray-200">
              <div className="mb-2">
                <div className="flex items-center gap-3 mb-2">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-blue-100 text-blue-800">
                    Step 1
                  </span>
                  <h2 className="text-lg font-semibold text-gray-900">
                    Connect Strava
                  </h2>
                </div>
                <p className="text-sm text-gray-600 leading-relaxed">
                  Connect your Strava account to sync your activities and create your plan
                </p>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700 mb-2">{error}</p>
                  <button
                    onClick={retryFetch}
                    className="text-sm text-red-600 hover:text-red-700 font-medium underline"
                  >
                    Try again
                  </button>
                </div>
              )}

              {isLoading ? (
                <div className="flex flex-col items-center py-4">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <p className="text-sm text-gray-600 mt-2">Loading...</p>
                </div>
              ) : (
                <StravaConnectSection
                  isSyncing={isSyncing}
                  isComplete={isComplete}
                  userId={userId}
                  onConnectClick={handleConnectClick}
                />
              )}
            </div>

            {/* Step 2 Card - Separate from Step 1 */}
            {isComplete && !isLoading && !isSyncing && (
              <div className="bg-gray-50 rounded-lg p-5 md:p-6 border border-gray-200 mt-6">
                <div className="mb-3">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-blue-100 text-blue-800">
                      Step 2
                    </span>
                    <h2 className="text-lg font-semibold text-gray-900">
                      Complete Your Profile
                    </h2>
                  </div>
                  <p className="text-sm text-gray-600 leading-relaxed">
                    Tell us a bit about yourself
                  </p>
                </div>
                <button
                  onClick={handleNavigateToOnboarding}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 shadow-md hover:shadow-lg cursor-pointer flex items-center justify-center gap-2"
                >
                  <span>Continue</span>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </button>
              </div>
            )}
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
