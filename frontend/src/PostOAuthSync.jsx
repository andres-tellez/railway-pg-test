import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const API = import.meta.env.VITE_BACKEND_URL;

export default function PostOAuthSync() {
  const [status, setStatus] = useState("syncing");
  const navigate = useNavigate();

  useEffect(() => {
    async function saveUserProfile(athleteId) {
      const name = localStorage.getItem("user_name");
      const email = localStorage.getItem("user_email");

      if (!athleteId || (!name && !email)) return;

      try {
        const response = await fetch(`${API}/auth/profile`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ athlete_id: athleteId, name, email }),
        });

        const result = await response.json();
        console.log("✅ Profile sync result:", result);
      } catch (err) {
        console.error("❌ Profile sync failed", err);
      }
    }

    async function fetchAthleteAndSync() {
      const params = new URLSearchParams(window.location.search);
      if (!params.get("authed")) return;

      try {
        const res = await fetch(`${API}/auth/whoami`);
        const data = await res.json();
        if (res.ok && data.athlete_id) {
          await saveUserProfile(data.athlete_id);
          setStatus("done");

          // ⏳ Wait 1.5s then redirect to /ask
          setTimeout(() => {
            navigate("/ask");
          }, 1500);
        } else {
          setStatus("error");
        }
      } catch (err) {
        console.error("❌ Failed to get athlete_id", err);
        setStatus("error");
      }
    }

    fetchAthleteAndSync();
  }, [navigate]);

  return (
    <div className="p-6 text-center max-w-lg mx-auto">
      <h2 className="text-2xl font-bold mb-4">Welcome to SmartCoach!</h2>
      {status === "syncing" && (
        <>
          <p className="text-gray-700">We’re syncing your Strava data...</p>
          <div className="mt-6 animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent mx-auto" />
        </>
      )}
      {status === "done" && (
        <p className="text-green-600 mt-4">✅ Sync complete! Redirecting...</p>
      )}
      {status === "error" && (
        <p className="text-red-600 mt-4">
          ❌ Something went wrong. Please try again.
        </p>
      )}
    </div>
  );
}
