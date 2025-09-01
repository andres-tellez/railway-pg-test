import React, { useEffect, useState } from "react";
import UserInfoCard from "../components/UserInfoCard";
import StatusTable from "../components/StatusTable";

export default function DashboardPage() {
  const [identity, setIdentity] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [activityCount, setActivityCount] = useState<number | null>(null);

  useEffect(() => {
    async function fetchData() {
      const resUser = await fetch("/api/user");
      const dataUser = await resUser.json();
      const resIdentity = await fetch("/api/user/identity");
      const dataIdentity = await resIdentity.json();
      const resActivities = await fetch("/api/strava/activities/status");
      const dataActivities = await resActivities.json();

      setStatus(dataUser);
      setIdentity(dataIdentity);
      setActivityCount(dataActivities.recentActivitiesCount);
    }
    fetchData();
  }, []);

  if (!identity || !status || activityCount === null) {
    return <div className="p-6">Loading…</div>;
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
          onboard: () => window.location.href = "/onboarding",
          connectStrava: () => window.location.href = "/auth/strava",
          fetchActivities: async () => {
            await fetch("/api/strava/sync", { method: "POST" });
            window.location.reload();
          },
        }}
      />
    </div>
  );
}
