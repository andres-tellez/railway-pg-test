import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const steps = [
  "Starting sync...",
  "Verifying session...",
  "Saving profile...",
  "Triggering ingestion...",
  "Redirecting to Ask Coach...",
];

export default function PostOAuthSuccess() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState("loading"); // 'loading' | 'error' | 'success'

  useEffect(() => {
    async function saveUserProfile(athleteId) {
      const name = localStorage.getItem("user_name");
      const email = localStorage.getItem("user_email");
      if (!athleteId || (!name && !email)) return;

      setStep(2); // Saving profile
      try {
        const res = await fetch("/auth/profile", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ athlete_id: athleteId, name, email }),
        });
        if (!res.ok) throw new Error("Failed to save profile");
      } catch (err) {
        console.error("❌ Profile sync failed", err);
        setStatus("error");
      }
    }

    async function fetchAthleteAndSync() {
      const params = new URLSearchParams(window.location.search);
      if (!params.get("authed")) return;

      setStep(1); // Verifying session
      try {
        const res = await fetch("/auth/whoami");
        const data = await res.json();

        if (res.ok && data.athlete_id) {
          await saveUserProfile(data.athlete_id);

          setStep(3); // Triggering ingestion
          const ingestRes = await fetch(`/admin/trigger-ingest/${data.athlete_id}`, {
            method: "POST",
          });

          if (ingestRes.ok) {
            setStep(4); // Redirecting
            setStatus("success");
            setTimeout(() => navigate("/ask"), 2000);
          } else {
            console.error("⚠️ Ingestion failed");
            setStatus("error");
          }
        } else {
          console.error("❌ No athlete_id returned");
          setStatus("error");
        }
      } catch (err) {
        console.error("❌ Error verifying session", err);
        setStatus("error");
      }
    }

    fetchAthleteAndSync();
  }, [navigate]);

  const getProgressColor = () => {
    if (status === "success") return "stroke-green-400";
    if (status === "error") return "stroke-red-500";
    return "stroke-blue-500";
  };

  return (
    <div className="p-8 text-center text-white bg-black min-h-screen flex flex-col items-center justify-center">
      <h1 className="text-3xl font-bold mb-6">🎉 Welcome to SmartCoach!</h1>
      <p className="text-lg mb-4">{steps[step]}</p>

      {/* Animated Circle Progress */}
      <div className="relative w-24 h-24 mb-6">
        <svg className="w-full h-full" viewBox="0 0 36 36">
          <path
            className="stroke-gray-700"
            d="M18 2.0845a15.9155 15.9155 0 1 1 0 31.831"
            fill="none"
            strokeWidth="4"
          />
          <path
            className={getProgressColor()}
            d={`M18 2.0845
              a 15.9155 15.9155 0 
              1 1 0 31.831
              a 15.9155 15.9155 0 
              1 1 0 -31.831`}
            fill="none"
            strokeDasharray={`${(step / (steps.length - 1)) * 100}, 100`}
            strokeLinecap="round"
            strokeWidth="4"
          />
        </svg>
      </div>

      {/* Step Descriptions */}
      <div className="w-64">
        {steps.map((label, index) => (
          <div
            key={index}
            className={`text-sm py-1 ${
              index === step
                ? "text-blue-400 font-semibold"
                : index < step
                ? "text-green-400 line-through"
                : "text-gray-500"
            }`}
          >
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
