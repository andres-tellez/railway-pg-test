import React, { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { AuthGuard } from "@/components/AuthGuard";
import { useApiClient } from "@/utils/apiClient";
import { useAuthSetup } from "@/hooks/useAuthSetup";

type PlanResponse = {
  plan_id: string;
  plan_name?: string;
  start_date: string;
  race_date: string;
  race_distance?: string;
  notes?: string;
  workouts: Array<{
    date: string;
    workout_type: string;
    intensity?: string;
    description?: string;
    miles: number;
    target_zone?: string;
    target_hr?: string;
    phase?: string;
  }>;
};

type WeekData = {
  weekNumber: number;
  weekStartDate: Date;
  phase: string;
  workouts: Record<string, number>; // day -> miles
  workoutDetails: Record<string, { workout_type: string; target_hr?: string; target_zone?: string }>; // day -> workout details
  total: number;
};

export default function PlanOverviewTable() {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady || !userId) return;

    const fetchPlan = async () => {
      try {
        setLoading(true);
        const res = await api.get<PlanResponse>("/api/plan/current");
        setPlan(res.data);
        setError(null);
      } catch (err: any) {
        console.error("Failed to fetch plan:", err);
        if (err.response?.status === 404) {
          setError("No active plan found. Create a plan to get started.");
        } else {
          setError("Failed to load plan. Please try again.");
        }
        setPlan(null);
      } finally {
        setLoading(false);
      }
    };

    fetchPlan();
  }, [isReady, userId, api]);

  // Helper to normalize day names
  const normalizeDay = (day: string | undefined): string => {
    if (!day) return "";
    const d = day.toLowerCase();
    if (d.startsWith("mon")) return "Mon";
    if (d.startsWith("tue")) return "Tue";
    if (d.startsWith("wed")) return "Wed";
    if (d.startsWith("thu")) return "Thu";
    if (d.startsWith("fri")) return "Fri";
    if (d.startsWith("sat")) return "Sat";
    if (d.startsWith("sun")) return "Sun";
    return "";
  };

  // Helper to get Monday of a week
  const getMondayOfWeek = (date: Date): Date => {
    const dayOfWeek = date.getDay();
    const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    const monday = new Date(date);
    monday.setDate(date.getDate() + mondayOffset);
    monday.setHours(0, 0, 0, 0);
    return monday;
  };

  // Helper to parse ISO date safely
  const parseISODate = (dateStr: string): Date => {
    return new Date(dateStr + "T00:00:00");
  };

  // Group workouts by week
  const weeks = useMemo(() => {
    if (!plan || !plan.workouts || plan.workouts.length === 0) return [];

    const weekMap = new Map<string, WeekData>();
    const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    plan.workouts.forEach((workout) => {
      const workoutDate = parseISODate(workout.date);
      const monday = getMondayOfWeek(workoutDate);
      const weekKey = monday.toISOString().split("T")[0];

      if (!weekMap.has(weekKey)) {
        weekMap.set(weekKey, {
          weekNumber: 0, // Will calculate later
          weekStartDate: monday,
          phase: "",
          workouts: {
            Mon: 0,
            Tue: 0,
            Wed: 0,
            Thu: 0,
            Fri: 0,
            Sat: 0,
            Sun: 0,
          },
          workoutDetails: {
            Mon: { workout_type: "", target_hr: undefined, target_zone: undefined },
            Tue: { workout_type: "", target_hr: undefined, target_zone: undefined },
            Wed: { workout_type: "", target_hr: undefined, target_zone: undefined },
            Thu: { workout_type: "", target_hr: undefined, target_zone: undefined },
            Fri: { workout_type: "", target_hr: undefined, target_zone: undefined },
            Sat: { workout_type: "", target_hr: undefined, target_zone: undefined },
            Sun: { workout_type: "", target_hr: undefined, target_zone: undefined },
          },
          total: 0,
        });
      }

      const week = weekMap.get(weekKey)!;
      const dayName = dayNames[workoutDate.getDay()];
      week.workouts[dayName] = (week.workouts[dayName] || 0) + workout.miles;
      week.total += workout.miles;
      // Store workout details including HR zone
      if (workout.workout_type || workout.target_hr || workout.target_zone) {
        week.workoutDetails[dayName] = {
          workout_type: workout.workout_type || "",
          target_hr: workout.target_hr,
          target_zone: workout.target_zone,
        };
      }
      // Store phase from workout (use the stored phase from database, not recalculated)
      // If multiple workouts in the same week have different phases, use the first one
      // (in practice, all workouts in a week should have the same phase)
      if (workout.phase && !week.phase) {
        week.phase = workout.phase;
      }
    });

    // Sort weeks by date and assign week numbers
    const sortedWeeks = Array.from(weekMap.values()).sort(
      (a, b) => a.weekStartDate.getTime() - b.weekStartDate.getTime()
    );

    // Assign week numbers and use stored phases from database
    const raceDate = plan.race_date ? parseISODate(plan.race_date) : null;
    sortedWeeks.forEach((week, idx) => {
      week.weekNumber = idx + 1;
      const isLastWeek = idx === sortedWeeks.length - 1;

      // Use stored phase from database
      // If no phase stored (shouldn't happen for approved plans), use fallback
      if (!week.phase) {
        if (isLastWeek && raceDate) {
          const weeksUntilRace = Math.ceil(
            (raceDate.getTime() - week.weekStartDate.getTime()) / (7 * 24 * 60 * 60 * 1000)
          );
          // If race is within this week, mark as Race Week
          if (weeksUntilRace <= 0) {
            week.phase = "Race Week";
          } else {
            week.phase = "Taper"; // Fallback for last week
          }
        } else {
          week.phase = "Base"; // Fallback for other weeks
        }
      } else {
        // Normalize phase name (database might have different casing)
        const phaseLower = week.phase.toLowerCase();
        if (phaseLower.includes("race")) {
          week.phase = "Race Week";
        } else {
          // Capitalize first letter: "base" -> "Base", "build" -> "Build", etc.
          week.phase = week.phase.charAt(0).toUpperCase() + week.phase.slice(1).toLowerCase();
        }
      }
    });

    return sortedWeeks;
  }, [plan]);



  const formatMDY = (date: Date) => {
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const dd = String(date.getDate()).padStart(2, "0");
    const yy = String(date.getFullYear()).slice(-2);
    return `${mm}/${dd}/${yy}`;
  };

  // Helper to get race distance in miles from race_distance string
  const getRaceDistanceMiles = (raceDistance?: string): number => {
    if (!raceDistance) return 26.2; // Default to marathon

    const raceLower = raceDistance.toLowerCase();
    if (raceLower.includes("half") || raceLower.includes("13.1")) {
      return 13.1;
    } else if (raceLower.includes("marathon") || raceLower.includes("26.2")) {
      return 26.2;
    }
    // Default to marathon if unknown
    return 26.2;
  };


  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gray-50 py-10">
          <div className="max-w-7xl mx-auto px-4">
            <div className="bg-white shadow rounded-lg p-6">
              <div className="text-center text-gray-600">Loading plan...</div>
            </div>
          </div>
        </div>
      </AuthGuard>
    );
  }

  if (error || !plan) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gray-50 py-10">
          <div className="max-w-7xl mx-auto px-4">
            <div className="bg-white shadow rounded-lg p-6">
              <h1 className="text-2xl font-bold text-gray-800 mb-4">Training Plan Overview</h1>
              <div className="text-red-600 mb-4">{error || "No plan found"}</div>
              <button
                onClick={() => navigate("/plan/new-v2")}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Create a Plan
              </button>
            </div>
          </div>
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50 py-10">
        <div className="max-w-7xl mx-auto px-4">
          <div className="bg-white shadow rounded-lg p-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6 gap-3">
              <div>
                {plan.plan_name && (
                  <p className="text-xs sm:text-sm font-semibold text-gray-500 mb-1">
                    {plan.plan_name}
                  </p>
                )}
                <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Training Plan Overview</h1>
                {plan.race_date && (
                  <p className="text-xs sm:text-sm text-gray-600 mt-1">
                    Race Date: {formatMDY(parseISODate(plan.race_date))}
                  </p>
                )}
              </div>
            </div>

            {/* Weeks Table */}
            {weeks.length === 0 ? (
              <div className="text-center text-gray-600 py-8">
                No workouts found in this plan.
              </div>
            ) : (
              <div className="overflow-x-auto -mx-4 sm:mx-0">
                <div className="inline-block min-w-full align-middle">
                  <div className="overflow-hidden">
                    <table className="border-collapse text-xs sm:text-sm w-full">
                  <thead>
                    <tr className="bg-slate-800 text-white">
                      <th className="py-1.5 px-2 sm:py-2 sm:px-3 text-center font-medium border border-slate-700">Week</th>
                      <th className="py-1.5 px-2 sm:py-2 sm:px-3 text-center font-medium border border-slate-700 whitespace-nowrap">Phase</th>
                      {['M','T','W','T','F','S','S'].map((d, i) => (
                        <th key={i} className="py-1.5 px-2 sm:py-2 sm:px-3 text-center font-medium border border-slate-700">{d}</th>
                      ))}
                      <th className="py-1.5 px-2 sm:py-2 sm:px-3 text-center font-medium border border-slate-700">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {weeks.map((week, idx) => {
                      const raceDate = plan.race_date ? parseISODate(plan.race_date) : null;
                      const isLastWeek = idx === weeks.length - 1;
                      // Check if this is the race week: either phase is "Race Week" or it's the last week with race in it
                      let isRaceWeek = week.phase === "Race Week" || week.phase?.toLowerCase().includes("race");
                      if (!isRaceWeek && isLastWeek && raceDate) {
                        const weeksUntilRace = Math.ceil(
                          (raceDate.getTime() - week.weekStartDate.getTime()) / (7 * 24 * 60 * 60 * 1000)
                        );
                        if (weeksUntilRace <= 0) {
                          isRaceWeek = true;
                          week.phase = "Race Week"; // Update phase for display
                        }
                      }
                      const phase = (week.phase || "").toLowerCase();

                      // Phase icons (matching PlanDraftPreview)
                      const getPhaseIcon = () => {
                        if (isRaceWeek) return "🏁";
                        if (phase.includes("taper")) return "🔋";
                        if (phase.includes("peak")) return "⚡";
                        if (phase.includes("build")) return "🔥";
                        if (phase.includes("base")) return "🧱";
                        return "";
                      };

                      // Row styling (matching PlanDraftPreview)
                      const getRowStyle = () => {
                        if (isRaceWeek) return "bg-amber-50 hover:bg-amber-100";
                        return "bg-white hover:bg-gray-50";
                      };

                      // Calculate which day of the week is the day before the race
                      let dayBeforeRace: string | null = null;
                      let raceDayName: string | null = null;
                      if (isRaceWeek && raceDate) {
                        const dayBeforeRaceDate = new Date(raceDate);
                        dayBeforeRaceDate.setDate(raceDate.getDate() - 1);
                        const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
                        dayBeforeRace = dayNames[dayBeforeRaceDate.getDay()];
                        raceDayName = dayNames[raceDate.getDay()];
                      }

                      // Calculate total for Race Week including the race distance
                      const raceDistanceMiles = getRaceDistanceMiles(plan.race_distance);
                      let displayTotal = week.total;
                      if (isRaceWeek && raceDayName) {
                        displayTotal = week.total + raceDistanceMiles;
                      }

                      return (
                        <tr
                          key={idx}
                          className={`${getRowStyle()} transition-colors`}
                        >
                          <td className="py-1.5 px-2 sm:py-2 sm:px-3 text-center border border-slate-200">
                            <span className="font-medium text-slate-700">{formatMDY(week.weekStartDate)}</span>
                          </td>
                          <td className={`py-1.5 px-2 sm:py-2 sm:px-3 text-center border border-slate-200 whitespace-nowrap font-medium ${
                            isRaceWeek ? "text-amber-700" : "text-slate-600"
                          }`}>
                            {isRaceWeek ? "Race" : (week.phase || "").trim()} {getPhaseIcon()}
                          </td>
                          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => {
                            // Hide workouts on the day before the race in Race Week
                            const shouldHide = isRaceWeek && day === dayBeforeRace;
                            // Show race distance on the race day
                            const isRaceDay = isRaceWeek && day === raceDayName;
                            const hasWorkout = week.workouts[day] > 0;

                            return (
                              <td
                                key={day}
                                className="py-1.5 px-2 sm:py-2 sm:px-3 text-center border border-slate-200 tabular-nums"
                              >
                                {shouldHide ? (
                                  <span className="text-slate-300">—</span>
                                ) : isRaceDay ? (
                                  <span className="text-slate-800 font-bold">{raceDistanceMiles}</span>
                                ) : hasWorkout ? (
                                  <span className="text-slate-800">{week.workouts[day]}</span>
                                ) : (
                                  <span className="text-slate-300">—</span>
                                )}
                              </td>
                            );
                          })}
                          <td className="py-1.5 px-2 sm:py-2 sm:px-3 text-center border border-slate-200 tabular-nums font-semibold text-slate-800">
                            {displayTotal > 0 ? (
                              Math.round(displayTotal)
                            ) : (
                              <span className="text-slate-300">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
