import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Loader2, CheckCircle, AlertTriangle } from "lucide-react";

const API = import.meta.env.VITE_BACKEND_URL;

export default function PostOAuthProgress() {
  const navigate = useNavigate();
  const [progress, setProgress] = useState("⏳ Starting sync...");
  const [step, setStep] = useState(0);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function saveUserProfile(athleteId) {
      const name = localStorage.getItem("user_name");
      const email = localStorage.getItem("user_email");
      if (!athleteId || (!name && !email)) return;

      setProgress("🧠 Saving profile...");
      setStep(1);

      try {
        const response = await fetch(`${API}/auth/profile`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include", // ✅ added
          body: JSON.stringify({ athlete_id: athleteId, name, email }),
        });
        const result = await response.json();
        console.log("✅ Profile synced:", result);
      } catch (err) {
        console.error("❌ Profile sync failed", err);
        setError("Failed to save user profile");
      }
    }

    async function fetchAthleteAndSync() {
      const params = new URLSearchParams(window.location.search);
      if (!params.get("authed")) return;

      setProgress("🔍 Verifying session...");
      setStep(0);

      try {
        const res = await fetch(`${API}/auth/whoami`, {
          method: "GET",
          credentials: "include", // ✅ added
        });
        const data = await res.json();

        if (res.ok && data.athlete_id) {
          await saveUserProfile(data.athlete_id);

          setProgress("📥 Syncing activities from Strava...");
          setStep(2);

          try {
            const ingestRes = await fetch(`${API}/admin/trigger-ingest/${data.athlete_id}`, {
              method: "POST",
              credentials: "include", // ✅ added
            });
            const ingestResult = await ingestRes.json();

            if (ingestRes.ok) {
              console.log("✅ Ingestion triggered:", ingestResult);
              setProgress("✅ All done! Redirecting shortly...");
              setStep(3);
              setTimeout(() => navigate("/ask"), 2500);
            } else {
              console.warn("⚠️ Trigger failed:", ingestResult);
              setProgress("⚠️ Trigger failed — check console");
              setError("Ingestion trigger failed");
            }
          } catch (syncErr) {
            console.error("❌ Trigger error:", syncErr);
            setProgress("❌ Error syncing activities");
            setError("Sync error");
          }
        } else {
          console.error("❌ No athlete_id returned:", data);
          setProgress("❌ Session invalid");
          setError("Session verification failed");
        }
      } catch (err) {
        console.error("❌ Error verifying session:", err);
        setProgress("❌ Error verifying session");
        setError("Session error");
      }
    }

    fetchAthleteAndSync();
  }, [navigate]);

  const steps = [
    "Verifying session",
    "Saving profile",
    "Triggering ingestion",
    "Redirecting to SmartCoach Ask"
  ];

  return (
    <div className="min-h-screen bg-black text-white flex flex-col items-center justify-center space-y-8">
      <h2 className="text-3xl font-semibold">🎉 Welcome to SmartCoach!</h2>
      <p className="text-gray-300">{progress}</p>

      <div className="relative w-24 h-24">
        {error ? (
          <AlertTriangle className="text-red-500 w-full h-full animate-pulse" />
        ) : step < 3 ? (
          <Loader2 className="w-full h-full animate-spin text-blue-400" />
        ) : (
          <CheckCircle className="text-green-400 w-full h-full" />
        )}
      </div>

      <div className="w-80 space-y-2">
        {steps.map((label, idx) => (
          <div
            key={idx}
            className={`flex items-center space-x-2 p-2 rounded-lg ${
              idx <= step ? "bg-blue-900" : "bg-gray-800"
            }`}
          >
            <motion.div
              className={`w-3 h-3 rounded-full ${
                idx < step
                  ? "bg-green-400"
                  : idx === step
                  ? "bg-blue-400 animate-pulse"
                  : "bg-gray-500"
              }`}
              layout
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
            />
            <span className="text-sm text-white">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
