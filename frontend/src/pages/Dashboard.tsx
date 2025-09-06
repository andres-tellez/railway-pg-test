// src/pages/Dashboard.tsx
import React, { useEffect, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "../utils/apiClient";

type UserInfo = {
  name: string;
  email: string;
  picture: string;
  hasOnboarded: boolean;
  hasStrava: boolean;
};

const Dashboard: React.FC = () => {
  const { isAuthenticated, isLoading, user } = useAuth0();
  const api = useApiClient();
  const [activityStatus, setActivityStatus] = useState<string>("Pending");

  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [activityCount, setActivityCount] = useState<number>(0);
  const [syncing, setSyncing] = useState(false);
  const [stravaHandled, setStravaHandled] = useState(false);

  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    const stravaSuccess = search.get("strava") === "success";

    if (stravaSuccess && isAuthenticated && !isLoading && !stravaHandled) {
      window.history.replaceState(null, "", "/dashboard");
      setStravaHandled(true);
      upsertUserIdentity();
      fetchUserData();
      fetchActivityStatus();
    }
  }, [isAuthenticated, isLoading, stravaHandled]);

  const upsertUserIdentity = async () => {
    try {
      await api.post("/user/identity");
      console.log("✅ Identity upserted");
    } catch (err) {
      console.error("❌ Failed to upsert identity:", err);
    }
  };

  const fetchUserData = async () => {
    try {
      const { data } = await api.get("/user");
      setUserInfo((prev) => ({
        name: data.name || user?.name || "",
        email: data.email || user?.email || "",
        picture: data.picture || user?.picture || "",
        hasOnboarded: data.hasOnboarded,
        hasStrava: prev?.hasStrava ?? false, // ← preserved safely
      }));
    } catch (err) {
      console.error("❌ Failed to fetch user data:", err);
    }
  };

  const fetchActivityStatus = async () => {
  try {
    const { data } = await api.get("/activities/status");

    setActivityCount(prev => {
      const newCount = data.recentActivitiesCount || 0;
      return newCount !== prev ? newCount : prev;
    });

    setActivityStatus(prev =>
      data.status && data.status !== prev ? data.status : prev
    );

    setUserInfo((prev) =>
      prev
        ? {
            ...prev,
            hasStrava: data.stravaConnected || false,
          }
        : {
            name: user?.name || "",
            email: user?.email || "",
            picture: user?.picture || "",
            hasOnboarded: false,
            hasStrava: data.stravaConnected || false,
          }
    );
  } catch (err) {
    console.error("❌ Failed to fetch activity status:", err);
  }
};

const syncActivities = async () => {
  console.log("🆗 Sync button clicked");

  try {
    setSyncing(true);
    console.log("🔄 Calling /activities/sync");

    // 🔧 Extract access_token from Auth0 localStorage entry
    const storageKey = Object.keys(localStorage).find((key) =>
      key.includes("@@auth0spajs@@")
    );

    if (!storageKey) throw new Error("No Auth0 storage key found");

    const tokenEntry = localStorage.getItem(storageKey);
    const parsed = tokenEntry ? JSON.parse(tokenEntry) : null;
    const accessToken = parsed?.body?.access_token;

    if (!accessToken) throw new Error("Access token not found");

    // 🔧 Manually call sync endpoint with token
    const response = await fetch("http://localhost:5000/api/activities/sync", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    const data = await response.json();

    console.log("✅ Sync success:", data);

    await new Promise((resolve) => setTimeout(resolve, 1500));

    await fetchActivityStatus();
    await fetchUserData();
  } catch (err) {
    console.error("❌ Activity sync failed:", err);
    alert("Sync failed. Check console for details.");
  } finally {
    setSyncing(false);
  }
};





  useEffect(() => {
    console.log("🔍 Auth state:", { isAuthenticated, isLoading });

    if (isAuthenticated && !isLoading) {
      upsertUserIdentity();
      fetchUserData();
      fetchActivityStatus();
    }
  }, [isAuthenticated, isLoading]);



  if (isLoading) return <div className="p-6">🔄 Loading auth...</div>;
  if (!isAuthenticated) return <div className="p-6 text-red-600">❌ Not authenticated</div>;
  if (!userInfo) return <div className="p-6">🔍 Loading user info...</div>;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold">🏁 Dashboard</h1>
      </div>

      <div className="bg-white shadow rounded-lg p-6 flex items-center space-x-4">
        <img src={userInfo.picture} className="w-20 h-20 rounded-full" alt="User Avatar" />
        <div>
          <p className="text-xl font-semibold">{userInfo.name}</p>
          <p className="text-gray-600">{userInfo.email}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {[
          {
            label: "Onboarding Complete",
            status: userInfo.hasOnboarded,
            actionLabel: "Complete Onboarding",
            onClick: () => (window.location.href = "/onboarding"),
          },
          {
            label: "Strava Connected",
            status: userInfo.hasStrava,
            actionLabel: "Connect Strava",
            onClick: () => {
              const apiBase = import.meta.env.VITE_API_BASE_URL;
              const userId = encodeURIComponent(user?.sub || "");
              window.location.href = `${apiBase}/auth/strava-login?user_id=${userId}`;
            },
          },
          {
            label: "10+ Activities Found",
            status: activityStatus === "Complete",
            actionLabel: "Sync Activities",
            onClick: syncActivities,
          },
          {
            label: "Authenticated",
            status: true,
          },
        ].map(({ label, status, actionLabel, onClick }, idx) => (
          <div key={idx} className="bg-white shadow rounded-lg p-4 flex flex-col justify-between">
            <div>
              <h2 className="text-lg font-medium">{label}</h2>
              <p className="mt-2">
                {status ? (
                  <span className="text-green-600 font-bold">✅ Completed</span>
                ) : (
                  <span className="text-red-500 font-bold">⏳ Pending</span>
                )}
              </p>
            </div>
            {actionLabel && !status && (
              <button
                onClick={() => {
                  console.log(`🖱 Button clicked: ${label}`);
                  onClick?.();
                }}
                className="mt-4 bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:bg-gray-400"
                disabled={syncing}
              >
                {syncing && label === "10+ Activities Found" ? "Syncing…" : actionLabel}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default Dashboard;
