import React, { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { AuthGuard } from "@/components/AuthGuard";
import { useApiClient } from "@/utils/apiClient";
import { useAuthSetup } from "@/hooks/useAuthSetup";

type PlanResponse = {
  plan_id: string;
  start_date: string;
  race_date: string;
  notes?: string;
  workouts: Array<{
    date: string;
    workout_type: string;
    intensity?: string;
    description?: string;
    miles: number;
    target_zone?: string;
    target_hr?: string;
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
    });

    // Sort weeks by date and assign week numbers
    const sortedWeeks = Array.from(weekMap.values()).sort(
      (a, b) => a.weekStartDate.getTime() - b.weekStartDate.getTime()
    );

    // Determine phases based on weeks until race
    const raceDate = plan.race_date ? parseISODate(plan.race_date) : null;
    sortedWeeks.forEach((week, idx) => {
      week.weekNumber = idx + 1;
      const isLastWeek = idx === sortedWeeks.length - 1;

      if (raceDate) {
        const weeksUntilRace = Math.ceil(
          (raceDate.getTime() - week.weekStartDate.getTime()) / (7 * 24 * 60 * 60 * 1000)
        );

        // If it's the last week or race is within this week, mark as Race Week
        if (isLastWeek || weeksUntilRace <= 0) {
          week.phase = "Race Week";
        } else if (weeksUntilRace <= 3) {
          week.phase = "Taper";
        } else if (weeksUntilRace <= 10) {
          week.phase = "Peak";
        } else if (weeksUntilRace <= 16) {
          week.phase = "Build";
        } else {
          week.phase = "Base";
        }
      } else {
        // Default phase assignment if no race date
        if (isLastWeek) {
          week.phase = "Race Week";
        } else if (idx >= sortedWeeks.length - 3) {
          week.phase = "Taper";
        } else if (idx >= sortedWeeks.length - 10) {
          week.phase = "Peak";
        } else if (idx >= sortedWeeks.length - 16) {
          week.phase = "Build";
        } else {
          week.phase = "Base";
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

  // Helper to extract just the HR zone (Z1, Z2, etc.) from target_hr
  const extractHRZone = (target_hr?: string): string => {
    if (!target_hr) return "";

    // Extract zone pattern from target_hr (usually "Z2 (120-150 bpm)" or "Z2-Z3 (120-150 bpm)")
    const zoneMatch = target_hr.match(/Z[1-5](-Z[1-5])?/);
    if (zoneMatch) {
      return zoneMatch[0];
    }

    return "";
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
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold text-gray-800">Training Plan Overview</h1>
                {plan.race_date && (
                  <p className="text-sm text-gray-600 mt-1">
                    Race Date: {formatMDY(parseISODate(plan.race_date))}
                  </p>
                )}
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => navigate("/plan/overview")}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  Calendar View
                </button>
              </div>
            </div>

            {/* Weeks Table */}
            {weeks.length === 0 ? (
              <div className="text-center text-gray-600 py-8">
                No workouts found in this plan.
              </div>
            ) : (
              <div className="overflow-x-auto flex justify-center">
                <table className="border border-gray-200 text-sm" style={{ width: 'auto' }}>
                  <thead>
                    <tr className="bg-gray-50 text-gray-700">
                      <th className="border p-2 text-center" style={{ width: '90px' }}>Week</th>
                      <th className="border p-2 text-center hidden sm:table-cell" style={{ width: '80px' }}>Phase</th>
                      {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                        <th key={d} className="border p-2 text-center" style={{ width: '50px' }}>
                          <span className="block sm:hidden">{d[0]}</span>
                          <span className="hidden sm:block">{d}</span>
                        </th>
                      ))}
                      <th className="border p-2 text-center" style={{ width: '60px' }}>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {weeks.map((week, idx) => {
                      const isRaceWeek = week.phase === "Race Week";
                      const raceDate = plan.race_date ? parseISODate(plan.race_date) : null;

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

                      // Calculate total for Race Week including the marathon
                      let displayTotal = week.total;
                      if (isRaceWeek && raceDayName) {
                        displayTotal = week.total + 26.2;
                      }

                      return (
                        <tr
                          key={idx}
                          className={
                            isRaceWeek
                              ? "bg-amber-100 border-l-4 border-amber-400"
                              : "hover:bg-gray-50"
                          }
                        >
                          <td className="border p-2 align-top text-center">
                            <div className="font-medium">{formatMDY(week.weekStartDate)}</div>
                          </td>
                          <td
                            className={`border p-2 align-top text-center whitespace-nowrap hidden sm:table-cell ${
                              isRaceWeek ? "text-amber-900 font-semibold tracking-wide" : ""
                            }`}
                          >
                            {isRaceWeek ? "Race" : week.phase || ""}
                          </td>
                          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => {
                            // Hide workouts on the day before the race in Race Week
                            const shouldHide = isRaceWeek && day === dayBeforeRace;
                            // Show 26.2 on the race day
                            const isRaceDay = isRaceWeek && day === raceDayName;
                            const hasWorkout = week.workouts[day] > 0;
                            const workoutDetail = week.workoutDetails[day];
                            const hrZone = extractHRZone(workoutDetail?.target_hr);

                            return (
                              <td
                                key={day}
                                className="border p-2 align-top text-center"
                              >
                                {shouldHide ? (
                                  <span className="text-gray-400">—</span>
                                ) : isRaceDay ? (
                                  <div className="font-bold text-amber-900">26.2</div>
                                ) : hasWorkout ? (
                                  <div className="flex flex-col items-center">
                                    <div>{week.workouts[day]}</div>
                                    {hrZone && (
                                      <div className="text-[10px] text-gray-500 mt-0.5 leading-tight">
                                        {hrZone}
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  <span className="text-gray-400">—</span>
                                )}
                              </td>
                            );
                          })}
                          <td className="border p-2 align-top text-center">
                            {displayTotal > 0 ? (
                              Math.round(displayTotal)
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
