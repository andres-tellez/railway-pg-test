// frontend/src/pages/PlanDraftPreview.tsx

import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AuthGuard } from "@/components/AuthGuard";
import { useApiClient } from "@/utils/apiClient";

type DraftState = {
  draft?: {
    generated_plan?: any;
    validation?: any;
  };
  plan_request?: any;
};

export default function PlanDraftPreview() {
  const location = useLocation();
  const navigate = useNavigate();
  const api = useApiClient();

  const { draft, plan_request } = (location.state || {}) as DraftState;
  const [currentDraft, setCurrentDraft] = useState(draft);
  const [regenLoading, setRegenLoading] = useState(false);
  const generated = currentDraft?.generated_plan || {};
  const validation = currentDraft?.validation || {};

  const violations: any[] = validation?.violations || [];
  const hasErrors = violations.some((v) => (v?.severity || "").toLowerCase() === "error");

  const handleApprove = async () => {
    try {
      const res = await api.post("/api/plan/approve", {
        validation,
        plan_request,
      });
      const planId = res.data?.plan_id;
      if (planId) {
        navigate(`/plan/${planId}`, { replace: true });
      } else {
        navigate("/plan/overview", { replace: true });
      }
    } catch (e) {
      // Simple error fallback
      alert("Failed to approve plan. Please try again.");
    }
  };

  const handleBack = () => {
    navigate(-1);
  };

  const handleRegenerateConservative = async () => {
    try {
      setRegenLoading(true);
      const res = await api.post("/api/plan/draft", {
        ...plan_request,
      });
      setCurrentDraft(res.data?.draft);
    } catch (e) {
      alert("Failed to regenerate. Please try again.");
    } finally {
      setRegenLoading(false);
    }
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50 py-10">
        <div className="max-w-4xl mx-auto bg-white shadow p-6 rounded-lg">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-bold text-gray-800">Draft Plan Preview</h1>
            <div className="space-x-3 flex items-center">
              <button
                onClick={handleBack}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
              >
                Back
              </button>
              <button
                onClick={handleApprove}
                disabled={hasErrors}
                className={`px-4 py-2 rounded-lg text-white ${hasErrors ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"}`}
                title={hasErrors ? "Fix errors before approving" : "Approve & Save"}
              >
                Approve & Save
              </button>
              {hasErrors && (
                <span
                  className="ml-1 inline-flex items-center text-sm text-red-700 cursor-help"
                  title={(validation?.violations || [])
                    .filter((v: any) => (v?.severity || "").toLowerCase() === "error")
                    .map((v: any, i: number) => `${i + 1}. ${v?.rule || "Rule"}: ${v?.details || ""}`)
                    .join("\n") || "Blocking validation errors present"}
                >
                  Why?
                </span>
              )}
            </div>
          </div>

          {/* Summary */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800">Summary</h2>
            <p className="text-gray-700">{generated?.plan_name || "Unnamed Plan"}</p>
          </div>

          {/* Validation */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800">Validation</h2>
            {violations.length === 0 ? (
              <p className="text-green-700">No issues detected.</p>
            ) : (
              <ul className="space-y-2">
                {violations.map((v, i) => (
                  <li key={i} className={`p-3 rounded ${ (v?.severity||"").toLowerCase()==="error" ? "bg-red-50 border border-red-200" : "bg-yellow-50 border border-yellow-200" }`}>
                    <div className="font-medium text-gray-800">{v?.rule || "Rule"} ({v?.severity})</div>
                    <div className="text-gray-700 text-sm">{v?.details}</div>
                    {v?.suggestion && (
                      <div className="text-gray-600 text-sm mt-1">Suggestion: {v.suggestion}</div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {hasErrors && (
            <div className="mb-6 p-4 rounded border border-red-200 bg-red-50">
              <div className="font-semibold text-red-800 mb-1">Approval blocked</div>
              <div className="text-red-700 text-sm">
                Fix the issues above by going back and adjusting your inputs, or try regenerating a safer draft.
              </div>
              <div className="mt-3">
                <button
                  onClick={handleRegenerateConservative}
                  disabled={regenLoading}
                  className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                >
                  {regenLoading ? "Regenerating…" : "Regenerate (Conservative)"}
                </button>
              </div>
            </div>
          )}

          {/* Weeks */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-800">Weeks</h2>
            {(generated?.weeks || []).map((w: any, idx: number) => (
              <div key={idx} className="border rounded p-4">
                <div className="font-semibold mb-2">Week {w?.week_number} — {w?.phase || ""}</div>
                <div className="text-sm text-gray-700 mb-2">Weekly Mileage: {w?.weekly_mileage ?? "-"}</div>
                <div className="space-y-2">
                  {(w?.workouts || []).map((wo: any, j: number) => (
                    <div key={j} className="bg-gray-50 rounded p-3">
                      <div className="font-medium">{wo?.day || "Day"}: {wo?.workout_type}</div>
                      <div className="text-sm text-gray-700">{wo?.distance_miles} mi • {wo?.pace_guidance || wo?.intensity}</div>
                      {wo?.workout_description && (
                        <div className="text-sm text-gray-600">{wo.workout_description}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
