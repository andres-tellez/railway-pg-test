import React, { useEffect, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import StravaLinkStatus from "@/components/StravaLinkStatus";

const Dashboard: React.FC = () => {
  const { logout, user, isAuthenticated, isLoading } = useAuth0();
  const [stravaError, setStravaError] = useState<string | null>(null);

  useEffect(() => {
    console.group("👤 Auth Debug");
    console.log("isAuthenticated:", isAuthenticated);
    console.log("isLoading:", isLoading);
    console.log("user:", user);
    console.groupEnd();
  }, [isAuthenticated, isLoading, user]);

  if (isLoading) return <div>🔄 Loading user...</div>;
  if (!isAuthenticated) return <div>⚠️ Not authenticated.</div>;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-green-700">🏁 Welcome to your Dashboard!</h1>
      <p className="mt-4 text-gray-600">You’ve successfully completed onboarding.</p>

      <div className="mt-6 text-sm text-gray-500">
        Logged in as: <strong>{user?.email}</strong>
      </div>

      {/* Show strava error gently */}
      {stravaError && (
        <div className="mt-4 p-4 bg-yellow-100 text-yellow-800 border border-yellow-300 rounded">
          ⚠️ Could not link with Strava. You can still use the app, but training sync won't work.
        </div>
      )}

      <div className="mt-6">
        <StravaLinkStatus onError={(msg) => setStravaError(msg)} />
      </div>

      <button
        className="mt-6 bg-red-600 text-white px-4 py-2 rounded"
        onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
      >
        🔒 Logout
      </button>
    </div>
  );
};

export default Dashboard;
