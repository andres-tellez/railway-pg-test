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

  useEffect(() => {
    if (!isAuthenticated) return;

    async function fetchData() {
      try {
        const { data: userStatus } = await api.get("/api/user");
        const { data: userIdentity } = await api.get("/api/user/identity");
        const { data: activities } = await api.get("/api/strava/activities/status");

        setStatus(userStatus);
        setIdentity(userIdentity);
        setActivityCount(activities.recentActivitiesCount);
      } catch (error) {
        console.error("❌ Failed to fetch dashboard data:", error);
      }
    }

    fetchData();
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
            await api.post("/api/strava/sync");
            window.location.reload();
          },
        }}
      />
    </div>
  );
}
