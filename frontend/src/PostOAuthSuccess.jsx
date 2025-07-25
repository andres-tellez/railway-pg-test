import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const API = import.meta.env.VITE_BACKEND_URL;

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
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    async function saveUserProfile(athleteId) {
      const name = localStorage.getItem("user_name");
      const email = localStorage.getItem("user_email");

      console.log("📤 Saving profile with:", { athleteId, name, email });

      if (!athleteId) {
        console.error("❌ saveUserProfile: athleteId is missing");
        return;
      }

      if (!name && !email) {
        console.warn("⚠️ saveUserProfile: no user_name or user_email in localStorage");
        return;
      }

      setStep(2);
      try {
        const res = await fetch(`${API}/auth/profile`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ athlete_id: athleteId, name, email }),
        });

        if (!res.ok) throw new Error("Failed to save profile");

        console.log("✅ Profile saved");
      } catch (err) {
        console.error("❌ Error saving profile", err);
        setStatus("error");
      }
    }

    async function triggerIngestion(athleteId) {
      setStep(3);
      try {
        const ingestRes = await fetch(`${API}/auth/trigger-ingest/${athleteId}`, {
          method: "POST",
          credentials: "include",
        });

        const result = await ingestRes.json().catch(() => null);
        console.log("📦 Ingestion response:", result);

        if (!ingestRes.ok) {
          console.error("❌ Ingestion failed", result);
          setStatus("error");
          return;
        }

        setStep(4);
        setStatus("success");
        setTimeout(() => navigate("/ask"), 2000);
      } catch (err) {
        console.error("❌ Ingestion error", err);
        setStatus("error");
      }
    }

    async function fetchAthleteAndSync() {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");

      console.log("🔧 ENV VITE_BACKEND_URL =", API);
      console.log("📥 OAuth code =", code);

      if (!code) {
        console.error("❌ No code found in URL");
        setStatus("error");
        return;
      }

      try {
        console.log("🌐 POST /auth/callback...");
        const tokenRes = await fetch(`${API}/auth/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ code }),
        });

        const rawText = await tokenRes.text();
        console.log("🔍 /auth/callback response:", tokenRes.status, rawText);

        if (!tokenRes.ok) {
          throw new Error(`Token exchange failed: ${rawText}`);
        }

        setStep(1);

        console.log("👤 GET /auth/whoami...");
        const res = await fetch(`${API}/auth/whoami`, {
          method: "GET",
          credentials: "include",
        });

        const whoamiText = await res.text();
        console.log("🙋 whoami raw response:", whoamiText);

        if (!res.ok) {
          throw new Error(`whoami failed: ${res.status}`);
        }

        const data = JSON.parse(whoamiText);
        const athleteId = data.athlete_id;

        if (!athleteId) {
          console.error("❌ No athlete_id returned");
          setStatus("error");
          return;
        }

        await saveUserProfile(athleteId);
        await triggerIngestion(athleteId);
      } catch (err) {
        console.error("❌ Error during OAuth sync process", err);
        setStatus("error");
      }
    }

    console.log("🚀 PostOAuthSuccess mounted");
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
