// src/pages/DashboardPage.tsx
import React, { useEffect, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import UserInfoCard from "../components/UserInfoCard";
import StatusTable from "../components/StatusTable";
import { useApiClient } from "../utils/apiClient";

export default function DashboardPage() {
  const { isLoading, isAuthenticated } = useAuth0();
  const api = useApiClient();

  const [identity, setIdentity] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [activityCount, setActivityCount] = useState<number | null>(null);
  const [syncing, setSyncing] = useState(false);

  // 🔁 Optional: clear ?strava=success from URL after handling
  const clearStravaSuccessParam = () => {
    const url = new URL(window.location.href);
    if (url.searchParams.has("strava")) {
      url.searchParams.delete("strava");
      window.history.replaceState({}, document.title, url.pathname);
    }
  };

  // 🧠 Reusable dashboard data loader
  const fetchDashboardData = async () => {
    try {
      const [{ data: userStatus }, { data: userIdentity }, { data: activities }] = await Promise.all([
        api.get("/api/user"),
        api.get("/api/user/identity"),
        api.get("/api/strava/activities/status"),
      ]);
      setStatus(userStatus);
      setIdentity(userIdentity);
      setActivityCount(activities.recentActivitiesCount);
    } catch (error) {
      console.error("❌ Failed to fetch dashboard data:", error);
    }
  };

  // 🧠 Optionally handle ?strava=success
  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    if (search.get("strava") === "success") {
      console.log("✅ Detected strava=success — syncing identity...");
      api.post("/api/user/identity")
        .then(() => {
          fetchDashboardData();
        })
        .finally(clearStravaSuccessParam);
    }
  }, [api]);

  // 🧠 Load dashboard once authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchDashboardData();
  }, [api, isAuthenticated]);

  if (isLoading || !isAuthenticated) {
    return <div className="p-6">🔐 Loading user info...</div>;
  }

  if (!identity || !status || activityCount === null) {
    return <div className="p-6">📊 Loading dashboard data…</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold">🔑 Dashboard (Your Hub)</h1>
      <UserInfoCard user={identity} />
      <StatusTable
        status={{
          authenticated: true,
          hasOnboarded: status.hasOnboarded,
          hasStrava: status.hasStrava,
          hasActivities: activityCount >= 10,
        }}
        actions={{
          onboard: () => (window.location.href = "/onboarding"),
          connectStrava: () => (window.location.href = "/auth/strava"),
          fetchActivities: async () => {
            setSyncing(true);
            await api.post("/api/strava/sync");
            await fetchDashboardData();
            setSyncing(false);
          },
        }}
      />
    </div>
  );
}
