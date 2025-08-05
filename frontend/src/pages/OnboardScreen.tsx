import React, { useState } from "react";
import { getAccessToken, getAuthHeader, getUserIdFromToken } from "../utils/auth";

export default function OnboardScreen() {
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const token = getAccessToken();
    if (!token) {
      setError("⚠️ No access token found. Please log in first.");
      return;
    }

    const userId = getUserIdFromToken(token);
    if (!userId) {
      setError("⚠️ Invalid access token. Please re-login.");
      return;
    }

    const payload = { user_id: userId, name, goal };
    console.log("📤 Submitting onboarding payload:", payload);

    try {
      const apiBase = import.meta.env.VITE_BACKEND_URL;
      const res = await fetch(`${apiBase}/api/onboarding`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeader(),
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setSubmitted(true);
        setError(null);
      } else {
        const data = await res.json();
        setError(data?.error || "Submission failed");
        console.error("❌ API Error:", data);
      }
    } catch (err) {
      console.error("❌ Network Error:", err);
      setError("Network error occurred. Please try again.");
    }
  };

  return (
    <div className="max-w-xl mx-auto mt-12 p-6 bg-white shadow-xl rounded-2xl text-left">
      <h1 className="text-2xl font-bold mb-4">🏃 Onboarding Form</h1>

      {error && <p className="text-red-600 font-semibold mb-4">{error}</p>}

      {!submitted ? (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block font-semibold mb-1">Your Name</label>
            <input
              type="text"
              className="w-full border rounded px-3 py-2"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Goal (e.g. Run 5K)</label>
            <input
              type="text"
              className="w-full border rounded px-3 py-2"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="bg-blue-600 text-white px-6 py-2 rounded">
            Submit
          </button>
        </form>
      ) : (
        <p className="text-green-700 font-semibold mt-4">✅ Submitted successfully!</p>
      )}
    </div>
  );
}
