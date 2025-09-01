import React, { useState } from "react";
import { useApiClient } from "../utils/apiClient";

export default function OnboardScreen() {
  const api = useApiClient();

  const [form, setForm] = useState({ name: "", goal: "" });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const res = await api.post("/api/onboarding", form);
      if (res.status === 200) {
        setSubmitted(true);
        setError(null);
      } else {
        setError(res.data?.error || "Submission failed.");
        console.error("❌ API error:", res.data);
      }
    } catch (err: any) {
      console.error("❌ Network error:", err);
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
              name="name"
              type="text"
              className="w-full border rounded px-3 py-2"
              value={form.name}
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Goal (e.g. Run 5K)</label>
            <input
              name="goal"
              type="text"
              className="w-full border rounded px-3 py-2"
              value={form.goal}
              onChange={handleChange}
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
