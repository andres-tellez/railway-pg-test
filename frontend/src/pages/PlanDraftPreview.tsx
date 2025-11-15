// frontend/src/pages/PlanDraftPreview.tsx

import React, { useMemo, useState } from "react";
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
    navigate(-1);
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

          {/* Summary */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800">Summary</h2>
            <p className="text-gray-700">{generated?.plan_name || "Unnamed Plan"}</p>
            {displayedTimezone && (
              <p className="text-sm text-gray-500 mt-1">
                Plan dates shown in <span className="font-medium">{displayedTimezone}</span>.
              </p>
            )}
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

          {/* Weeks Table */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-800">Weeks</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full border border-gray-200 text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-700">
                    <th className="border p-2 text-left">Week</th>
                    <th className="border p-2 text-left">Phase</th>
                    {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((d) => (
                      <th key={d} className="border p-2 text-center">{d}</th>
                    ))}
                    <th className="border p-2 text-center">Total</th>
                  </tr>
                  {(() => {
                    // Extract run types from first week's workouts to display in header
                    const firstWeek = (generated?.weeks || [])[0];
                    const runTypeMap: Record<string, string> = {};

                    if (firstWeek?.workouts && Array.isArray(firstWeek.workouts)) {
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

                      firstWeek.workouts.forEach((workout: any) => {
                        const day = normalize(workout.day);
                        if (day) {
                          const workoutType = workout.workout_type || '';
                          // Map to display names:
                          // "Easy / Recovery" -> "Easy/Recovery"
                          // "Aerobic" -> "Aerobic"
                          // "Endurance" -> "Endurance"
                          // "Long Run" -> "Long"
                          const shortType = workoutType
                            .replace('Easy / Recovery', 'Easy/Recovery')
                            .replace('Long Run', 'Long');
                          runTypeMap[day] = shortType || workoutType;
                        }
                      });
                    }

                    return (
                      <tr className="bg-gray-100 text-gray-600 text-xs">
                        <th className="border p-1"></th>
                        <th className="border p-1"></th>
                        {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((d) => (
                          <th key={d} className="border p-1 text-center font-normal">
                            {runTypeMap[d] || ''}
                          </th>
                        ))}
                        <th className="border p-1"></th>
                      </tr>
                    );
                  })()}
                </thead>
                <tbody>
                  {(generated?.weeks || []).map((w: any, idx: number) => {
                    // Helper: format date as MM/DD/YY
                    const formatMDY = (d?: Date) => {
                      if (!d) return '';
                      const mm = String(d.getMonth() + 1).padStart(2, '0');
                      const dd = String(d.getDate()).padStart(2, '0');
                      const yy = String(d.getFullYear()).slice(-2);
                      return `${mm}/${dd}/${yy}`;
                    };
                    // Determine Monday for this week
                    const parseISODate = (s?: string) => {
                      try {
                        if (!s) return undefined;
                        // Force UTC midnight parse safety
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
                    // Build day-to-items map from workouts
                    const dayToItems: Record<string, string[]> = { Mon: [], Tue: [], Wed: [], Thu: [], Fri: [], Sat: [], Sun: [] };

                    // Populate dayToItems from workouts if available
                    if (w?.workouts && Array.isArray(w.workouts)) {
                      w.workouts.forEach((workout: any) => {
                        const day = normalize(workout.day);
                        if (day && dayToItems[day] !== undefined) {
                          const miles = workout.distance_miles || workout.miles || 0;
                          const workoutType = workout.workout_type || '';
                          // Show miles for all workouts (not just long runs)
                          const displayText = miles > 0 ? `${miles}` : '';
                          if (displayText && miles > 0) {
                            dayToItems[day].push(displayText);
                          }
                        }
                      });
                    }

                    // Fallback: if no workouts but we have long_run_miles, show it in Sat or Sun
                    // This handles LR-only drafts where workouts haven't been generated yet
                    if ((!w?.workouts || w.workouts.length === 0) && w?.long_run_miles) {
                      const lr = Number(w.long_run_miles);
                      if (lr > 0) {
                        // Get training days from plan_request if available
                        const trainingDays = location.state?.plan_request?.training_days || [];
                        const normalizedTrainingDays = trainingDays.map((d: string) => normalize(d)).filter(Boolean);

                        // Prefer Sat, then Sun if they're in training days
                        if (normalizedTrainingDays.includes('Sat')) {
                          dayToItems['Sat'].push(`${lr}`);
                        } else if (normalizedTrainingDays.includes('Sun')) {
                          dayToItems['Sun'].push(`${lr}`);
                        } else if (normalizedTrainingDays.length > 0) {
                          // Fallback to last training day if no weekend days
                          const lastDay = normalizedTrainingDays[normalizedTrainingDays.length - 1];
                          if (dayToItems[lastDay] !== undefined) {
                            dayToItems[lastDay].push(`${lr}`);
                          }
                        }
                      }
                    }

                    const total = Number(w?.weekly_mileage ?? 0) || 0;
                    // Get week label (e.g., "Week 1 of Nov 4")
                    const weekLabel = w?.week_label || `Week ${w?.week_number ?? idx + 1}`;
                    const weekDisplay = formatMDY(mondayDate) || weekLabel;

                const isRaceWeek = (w?.phase || "").toLowerCase() === "race week";
                return (
                  <tr
                    key={idx}
                    className={
                      isRaceWeek
                        ? "bg-amber-100 border-l-4 border-amber-400"
                        : "hover:bg-gray-50"
                    }
                  >
                        <td className="border p-2 align-top">
                          <div className="font-medium">{weekDisplay}</div>
                        </td>
                    <td
                      className={`border p-2 align-top ${
                        isRaceWeek ? "text-amber-900 font-semibold tracking-wide" : ""
                      }`}
                    >
                      {isRaceWeek ? "Race Week 🎉" : w?.phase || ""}
                    </td>
                        {dayKeys.map((d) => (
                          <td key={d} className="border p-2 align-top text-center">
                            {dayToItems[d] && dayToItems[d].length > 0 ? (
                              <div className="space-y-1">
                                {dayToItems[d].map((t, i) => (
                                  <div key={i}>{t}</div>
                                ))}
                              </div>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                        ))}
                        <td className="border p-2 align-top text-center">{(typeof w?.weekly_mileage === 'number' ? Number(w.weekly_mileage) : <span className="text-gray-400">—</span>)}</td>
                      </tr>
                    );
                  })}

                  {/* Marathon Day Row */}
                  {currentDraft?.generated_plan?.race_metadata && (() => {
                    const raceDateStr = currentDraft.generated_plan.race_metadata.race_date;
                    let raceDate: Date | undefined;
                    try {
                      if (raceDateStr) {
                        raceDate = new Date(raceDateStr + 'T00:00:00');
                      }
                    } catch (e) {
                      // Ignore date parsing errors
                    }

                    const getRaceDayName = () => {
                      if (!raceDate) return '';
                      const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
                      return dayNames[raceDate.getDay()];
                    };

                    const formatMDY = (d?: Date) => {
                      if (!d) return '';
                      const mm = String(d.getMonth() + 1).padStart(2, '0');
                      const dd = String(d.getDate()).padStart(2, '0');
                      const yy = String(d.getFullYear()).slice(-2);
                      return `${mm}/${dd}/${yy}`;
                    };

                    return (
                      <tr className="bg-purple-50 border-t-2 border-purple-300">
                        <td className="border p-2 align-top font-semibold text-purple-800">
                          <div className="font-medium">{formatMDY(raceDate)}</div>
                        </td>
                        <td className="border p-2 align-top font-semibold text-purple-800">Race Day</td>
                        {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((d) => {
                          const isRaceDay = getRaceDayName() === d;
                          return (
                            <td key={d} className="border p-2 align-top text-center">
                              {isRaceDay ? (
                                <div className="font-bold text-purple-800">26.2</div>
                              ) : (
                                <span className="text-gray-400">—</span>
                              )}
                            </td>
                          );
                        })}
                        <td className="border p-2 align-top text-center font-semibold text-purple-800">26.2</td>
                      </tr>
                    );
                  })()}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
