import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useApiClient } from "../utils/apiClient";
import { format, parseISO, startOfWeek } from "date-fns";

type Workout = {
  id: number;
  date: string;
  workout_type: string;
  miles: number;
  intensity: string;
  description: string;
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
  const api = useApiClient();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

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
  }, [id]); // ✅ only depend on id, not api

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
                  <p className="text-sm text-gray-600">{w.description}</p>
                </div>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
