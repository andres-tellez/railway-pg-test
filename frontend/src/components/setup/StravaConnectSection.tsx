import React, { memo } from "react";
import StravaConnectButton from "../StravaConnectButton";
import StravaAttribution from "../StravaAttribution";

interface StravaConnectSectionProps {
  isSyncing: boolean;
  isComplete: boolean;
  userId: string | null;
  onConnectClick: () => void;
}

const StravaConnectSection: React.FC<StravaConnectSectionProps> = ({
  isSyncing,
  isComplete,
  userId,
  onConnectClick,
}) => {
  if (isSyncing) {
    return (
      <div className="flex flex-col items-center py-4">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <p className="text-sm text-gray-600 mt-2">Syncing your Strava data…</p>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className="flex flex-col items-center">
        <div className="flex items-center justify-center w-full mb-3">
          <div className="bg-green-100 rounded-full p-3">
            <svg className="w-8 h-8 text-green-600" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
          </div>
        </div>
        <p className="text-sm text-green-700 font-medium text-center mb-1.5 leading-relaxed">
          ✅ Strava account connected successfully
        </p>
        <p className="text-xs text-gray-500 text-center leading-relaxed">
          Your Strava data has been synced
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center">
      <StravaConnectButton
        onClick={onConnectClick}
        disabled={!userId}
      />
      <StravaAttribution className="mt-2" />
      <p className="text-sm text-gray-600 mt-3 text-center leading-relaxed">
        {userId
          ? "We'll download your recent runs from Strava to understand your fitness level and keep your plan updated automatically"
          : "Waiting for identity…"}
      </p>
    </div>
  );
};

// Memoize component to prevent unnecessary re-renders when props haven't changed
export const StravaConnectSectionMemoized = memo(StravaConnectSection);
export { StravaConnectSectionMemoized as StravaConnectSection };
