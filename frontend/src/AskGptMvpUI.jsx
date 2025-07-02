import React, { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

export default function AskGptMvpUI() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);

  const athleteId = 347085; // hardcoded for now

  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setResponse("");

    try {
      const res = await fetch("http://127.0.0.1:5000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question, athlete_id: athleteId }),
      });

      const data = await res.json();
      setResponse(data.response || "No response returned.");
    } catch (err) {
      console.error("Error:", err);
      setResponse("❌ Error contacting backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto mt-10 p-4">
      <Card className="p-4 shadow-xl">
        <CardContent className="space-y-4">
          <h1 className="text-2xl font-bold">SmartCoach Ask</h1>
          <Textarea
            placeholder="Ask a question about your training week..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="min-h-[100px]"
          />
          <Button onClick={handleAsk} disabled={loading}>
            {loading ? "Loading..." : "Ask CoachGPT"}
          </Button>
          {response && (
            <div className="mt-4 bg-gray-50 p-4 rounded-xl border text-sm whitespace-pre-line">
              {response}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
