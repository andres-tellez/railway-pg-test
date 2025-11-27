// frontend/src/pages/PlanDraftPreview.tsx

import React, { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AuthGuard } from "@/components/AuthGuard";
import { useApiClient } from "@/utils/apiClient";
import { normalizeWorkoutTypeDisplay } from "@/utils/workoutTypeUtils";

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

  // Spine quality validation (cutback spacing, progression safety, etc.)
  const spineQuality = validation?.spine_quality;
  const spineQualityIssues = spineQuality?.issues || [];
  const hasSpineQualityIssues = !spineQuality?.is_valid && spineQualityIssues.length > 0;

  const browserTimezone = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone,
    []
  );

  const planRequestWithTimezone = useMemo(() => {
    if (!plan_request) {
      return { user_timezone: browserTimezone };
    }
    return {
      ...plan_request,
      user_timezone: plan_request.user_timezone || browserTimezone,
    };
  }, [plan_request, browserTimezone]);

  const displayedTimezone =
    generated?.timezone ||
    planRequestWithTimezone.user_timezone ||
    browserTimezone;

  const handleApprove = async () => {
    try {
      const res = await api.post("/api/plan/approve", {
        validation: {
          validated_plan: generated,
        },
        plan_request: planRequestWithTimezone,
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
    // Pass form data back so user doesn't have to re-enter
    navigate("/plan/new-v2", {
      state: { savedFormData: plan_request }
    });
  };

  const handleRegenerateConservative = async () => {
    try {
      setRegenLoading(true);
      const res = await api.post("/api/plan/draft", {
        ...planRequestWithTimezone,
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
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Draft Plan Preview</h1>
            </div>
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
                className={`px-4 py-2 rounded-lg text-white ${
                  hasErrors
                    ? "bg-gray-400 cursor-not-allowed"
                    : "bg-blue-600 hover:bg-blue-700"
                }`}
                title={
                  hasErrors ? "Fix errors before approving" : "Approve & Save"
                }
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

          {/* Plan Name */}
          <div className="mb-6">
            <p className="text-lg font-semibold text-gray-800">
              {plan_request?.plan_name ||
               (plan_request?.race_name && plan_request?.training_days?.length
                 ? `${plan_request.race_name} - ${plan_request.training_days.length} day plan`
                 : plan_request?.race_name
                   ? `${plan_request.race_name} Training Plan`
                   : `${plan_request?.race_distance || "Marathon"} Plan`)}
            </p>
          </div>

          {/* Time Assessment */}
          {currentDraft?.time_assessment && (
            <div className={`mb-6 p-4 rounded border ${
              currentDraft.time_assessment.type === "warning"
                ? "border-yellow-300 bg-yellow-50"
                : "border-blue-200 bg-blue-50"
            }`}>
              <div className={`font-semibold mb-2 ${
                currentDraft.time_assessment.type === "warning"
                  ? "text-yellow-800"
                  : "text-blue-800"
              }`}>
                ⏱️ Training Time Assessment
              </div>
              <div className={`text-sm ${
                currentDraft.time_assessment.type === "warning"
                  ? "text-yellow-700"
                  : "text-blue-700"
              }`}>
                <p className="mb-2">{currentDraft.time_assessment.message}</p>
                {currentDraft.time_assessment.suggestion && (
                  <p className="text-xs italic mt-1">
                    <strong>Note:</strong> {currentDraft.time_assessment.suggestion}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Validation - Only show if there are issues */}
          {(violations.length > 0 || hasSpineQualityIssues) && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gray-800">Validation Issues</h2>

              {/* Plan Safety Validation (from PlanValidationServiceV2) */}
              {violations.length > 0 && (
                <div className="mb-4">
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
                </div>
              )}

              {/* Spine Quality Issues */}
              {hasSpineQualityIssues && (
                <ul className="space-y-2">
                  {spineQualityIssues.map((issue: string, i: number) => (
                    <li key={i} className="p-3 rounded bg-orange-50 border border-orange-200">
                      <div className="font-medium text-gray-800">⚠️ Structure Issue</div>
                      <div className="text-gray-700 text-sm">{issue}</div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

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

          {/* Weeks Table */}
          <div className="space-y-4">
            <div className="overflow-x-auto flex justify-center">
              <table className="border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-800 text-white">
                    <th className="py-2 px-3 text-center font-medium border border-slate-700">Week</th>
                    <th className="py-2 px-3 text-center font-medium border border-slate-700 whitespace-nowrap">Phase</th>
                    {['M','T','W','T','F','S','S'].map((d, i) => (
                      <th key={i} className="py-2 px-3 text-center font-medium border border-slate-700">{d}</th>
                    ))}
                    <th className="py-2 px-3 text-center font-medium border border-slate-700">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(generated?.weeks || []).map((w: any, idx: number) => {
                    const formatMDY = (d?: Date) => {
                      if (!d) return '';
                      const mm = String(d.getMonth() + 1).padStart(2, '0');
                      const dd = String(d.getDate()).padStart(2, '0');
                      const yy = String(d.getFullYear()).slice(-2);
                      return `${mm}/${dd}/${yy}`;
                    };
                    const parseISODate = (s?: string) => {
                      try {
                        if (!s) return undefined;
                        return new Date(`${s}T00:00:00`);
                      } catch {
                        return undefined;
                      }
                    };
                    const addDays = (d: Date, days: number) => {
                      const nd = new Date(d.getTime());
                      nd.setDate(nd.getDate() + days);
                      return nd;
                    };
                    let mondayDate: Date | undefined =
                      parseISODate(w?.week_start_date || w?.week_start);
                    if (!mondayDate && generated?.start_date) {
                      const start = parseISODate(generated.start_date);
                      if (start) mondayDate = addDays(start, idx * 7);
                    }
                    const dayKeys = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
                    const normalize = (day: string | undefined) => {
                      if (!day) return '';
                      const d = day.toLowerCase();
                      if (d.startsWith('mon')) return 'Mon';
                      if (d.startsWith('tue')) return 'Tue';
                      if (d.startsWith('wed')) return 'Wed';
                      if (d.startsWith('thu')) return 'Thu';
                      if (d.startsWith('fri')) return 'Fri';
                      if (d.startsWith('sat')) return 'Sat';
                      if (d.startsWith('sun')) return 'Sun';
                      return '';
                    };
                    const dayToItems: Record<string, string[]> = { Mon: [], Tue: [], Wed: [], Thu: [], Fri: [], Sat: [], Sun: [] };

                    if (w?.workouts && Array.isArray(w.workouts)) {
                      w.workouts.forEach((workout: any) => {
                        const day = normalize(workout.day);
                        if (day && dayToItems[day] !== undefined) {
                          const miles = workout.distance_miles || workout.miles || 0;
                          const displayText = miles > 0 ? `${miles}` : '';
                          if (displayText && miles > 0) {
                            dayToItems[day].push(displayText);
                          }
                        }
                      });
                    }

                    if ((!w?.workouts || w.workouts.length === 0) && w?.long_run_miles) {
                      const lr = Number(w.long_run_miles);
                      if (lr > 0) {
                        const trainingDays = location.state?.plan_request?.training_days || [];
                        const normalizedTrainingDays = trainingDays.map((d: string) => normalize(d)).filter(Boolean);
                        if (normalizedTrainingDays.includes('Sat')) {
                          dayToItems['Sat'].push(`${lr}`);
                        } else if (normalizedTrainingDays.includes('Sun')) {
                          dayToItems['Sun'].push(`${lr}`);
                        } else if (normalizedTrainingDays.length > 0) {
                          const lastDay = normalizedTrainingDays[normalizedTrainingDays.length - 1];
                          if (dayToItems[lastDay] !== undefined) {
                            dayToItems[lastDay].push(`${lr}`);
                          }
                        }
                      }
                    }

                    const weekLabel = w?.week_label || `Week ${w?.week_number ?? idx + 1}`;
                    const weekDisplay = formatMDY(mondayDate) || weekLabel;
                    const phase = (w?.phase || "").toLowerCase();
                    const isRaceWeek = phase === "race week";

                    // Phase icons
                    const getPhaseIcon = () => {
                      if (isRaceWeek) return "🏁";
                      if (phase.includes("taper")) return "🔋";
                      if (phase.includes("peak")) return "⚡";
                      if (phase.includes("build")) return "🔥";
                      if (phase.includes("base")) return "🧱";
                      return "";
                    };

                    // Clean row styling - only highlight race week
                    const getRowStyle = () => {
                      if (isRaceWeek) return "bg-amber-50 hover:bg-amber-100";
                      return "bg-white hover:bg-gray-50";
                    };

                    return (
                      <tr key={idx} className={`${getRowStyle()} transition-colors`}>
                        <td className="py-2 px-3 text-center border border-slate-200">
                          <span className="font-medium text-slate-700">{weekDisplay}</span>
                        </td>
                        <td className={`py-2 px-3 text-center border border-slate-200 whitespace-nowrap font-medium ${
                          isRaceWeek ? "text-amber-700" : "text-slate-600"
                        }`}>
                          {isRaceWeek ? "Race" : (w?.phase || "").trim()} {getPhaseIcon()}
                        </td>
                        {dayKeys.map((d) => (
                          <td key={d} className="py-2 px-3 text-center border border-slate-200 tabular-nums">
                            {dayToItems[d] && dayToItems[d].length > 0 ? (
                              <span className="text-slate-800">{dayToItems[d].join(', ')}</span>
                            ) : (
                              <span className="text-slate-300">—</span>
                            )}
                          </td>
                        ))}
                        <td className="py-2 px-3 text-center border border-slate-200 tabular-nums font-semibold text-slate-800">
                          {typeof w?.weekly_mileage === 'number' ? w.weekly_mileage : <span className="text-slate-300">—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
