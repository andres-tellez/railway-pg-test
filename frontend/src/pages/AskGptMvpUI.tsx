import React, { useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";


const API = import.meta.env.VITE_BACKEND_URL;

export default function AskGptMvpUI() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const { getAccessTokenSilently } = useAuth0();

  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setResponse("");

    try {
      const token = await getAccessTokenSilently();
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({ question }),
      });

      const data = await res.json();
      setResponse(data.response || data.error || "No response returned.");
    } catch (err) {
      console.error("Error:", err);
      setResponse("❌ Error contacting backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto mt-10 p-4">
      <div className="border rounded-xl shadow-xl p-6 bg-white">
        <h1 className="text-2xl font-bold mb-4">SmartCoach Ask</h1>
        <textarea
          placeholder="Ask a question about your training week..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="w-full min-h-[100px] p-2 border rounded-lg mb-4"
        />
        <button
          onClick={handleAsk}
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
        >
          {loading ? "Loading..." : "Ask CoachGPT"}
        </button>
        {response && (
          <div className="mt-4 bg-gray-50 p-4 rounded-xl border text-sm whitespace-pre-line">
            {response}
          </div>
        )}
      </div>
    </div>
  );
}
