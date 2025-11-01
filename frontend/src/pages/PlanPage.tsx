import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useApiClient } from "../utils/apiClient";
import { useAuthSetup } from "../hooks/useAuthSetup";
import { AuthGuard } from "../components/AuthGuard";
import { format, parseISO, startOfWeek } from "date-fns";

type Workout = {
  id: number;
  date: string;
  workout_type: string;
  miles: number;
  intensity: string;
  description: string;
  target_zone?: string;
  target_hr?: string;
  focus?: string;
  segments?: any;
};

type Plan = {
  id: number;
  plan_name: string;
  notes: string;
  race_date: string;
  race_distance: string;
  workouts: Workout[];
};

export default function PlanPage() {
  const { id } = useParams(); // plan id from URL
  const { isReady, userId } = useAuthSetup(); // ✅ Centralized auth (AuthGuard handles the rest)
  const api = useApiClient();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !isReady || !userId) return; // ✅ Wait for auth setup

    const fetchPlan = async () => {
      try {
        const res = await api.get(`/api/plan/${id}`);
        setPlan(res.data);
      } catch (err) {
        console.error("Failed to load plan:", err);
        setError("No plan found.");
      }
    };

    fetchPlan();
  }, [id, isReady, userId, api]); // ✅ Depend on auth setup

  if (error) {
    return <p className="p-6 text-red-600">❌ {error}</p>;
  }

  if (!plan) return <p className="p-6">Loading plan...</p>;

  // --- Group workouts by week ---
  const groupedByWeek = plan.workouts.reduce<Record<string, Workout[]>>(
    (acc, workout) => {
      const weekStart = format(
        startOfWeek(parseISO(workout.date), { weekStartsOn: 1 }),
        "yyyy-MM-dd"
      ); // Monday-based weeks
      if (!acc[weekStart]) acc[weekStart] = [];
      acc[weekStart].push(workout);
      return acc;
    },
    {}
  );

  const weekKeys = Object.keys(groupedByWeek).sort();

  return (
    <AuthGuard>
      <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">{plan.plan_name}</h1>
      <p className="mb-4 text-gray-700">{plan.notes}</p>
      <p className="mb-6">
        <strong>Race:</strong> {plan.race_distance} on {plan.race_date}
      </p>

      {weekKeys.map((week) => (
        <div key={week} className="mb-8">
          <h2 className="text-xl font-semibold mb-3">
            Week of {format(parseISO(week), "MMM d, yyyy")}
          </h2>
          <div className="space-y-3">
            {groupedByWeek[week]
              .sort((a, b) => a.date.localeCompare(b.date))
              .map((w) => (
                <div
                  key={w.id}
                  className="border rounded-lg p-4 bg-white shadow-sm"
                >
                  <p className="font-medium">
                    {format(parseISO(w.date), "EEE, MMM d")} — {w.workout_type} (
                    {w.miles} mi)
                  </p>
                  {w.target_zone && (
                    <p className="text-sm text-blue-700 font-medium mt-1">
                      Target pace: {w.target_zone}
                    </p>
                  )}
                  <p className="text-sm text-gray-600 mt-2">{w.description}</p>

                  {/* Show workout segments if available */}
                  {w.segments && w.segments.steps && Array.isArray(w.segments.steps) && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-xs font-semibold text-gray-700 mb-2">Workout Structure:</p>
                      <div className="space-y-1">
                        {w.segments.steps.map((step: any, idx: number) => (
                          <div key={idx} className="flex justify-between items-start text-xs">
                            <span className="text-gray-700">
                              {step.name} ({step.value} {step.durationType === 'DISTANCE' ? 'mi' : 'min'})
                            </span>
                            {step.intensity && (
                              <span className="ml-2 px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                                {step.intensity}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                      {w.segments.notes && (
                        <p className="text-xs text-gray-600 mt-2 italic">{w.segments.notes}</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
          </div>
        </div>
      ))}
      </div>
    </AuthGuard>
  );
}
