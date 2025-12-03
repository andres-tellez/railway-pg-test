import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useApiClient } from "../utils/apiClient";
import { useAuthSetup } from "../hooks/useAuthSetup";
import { AuthGuard } from "../components/AuthGuard";
import { format, parseISO, startOfWeek } from "date-fns";
import { useUnitSystem } from "../context/UnitSystemContext";
import { formatDistanceNumber, formatDistance, parseAndConvertPaceString } from "../utils/unitFormatters";

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
  const navigate = useNavigate();
  const { isReady, userId } = useAuthSetup(); // ✅ Centralized auth (AuthGuard handles the rest)
  const api = useApiClient();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedWorkouts, setExpandedWorkouts] = useState<Record<string, boolean>>({});

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
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold mb-2">{plan.plan_name}</h1>
          <p className="mb-4 text-gray-700">{plan.notes}</p>
          <p className="mb-6">
            <strong>Race:</strong> {plan.race_distance} on {plan.race_date}
          </p>
        </div>
        <button
          onClick={() => navigate("/plan/overview")}
          className="px-4 py-2 text-sm font-medium text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 transition-colors ml-4 whitespace-nowrap"
        >
          📊 View as Table
        </button>
      </div>

      {weekKeys.map((week, weekIdx) => (
        <div key={week} className="mb-8">
          <h2 className="text-xl font-semibold mb-3">
            Week of {format(parseISO(week), "MMM d, yyyy")}
          </h2>
          <div className="space-y-3">
            {groupedByWeek[week]
              .sort((a, b) => a.date.localeCompare(b.date))
              .map((w) => (
                <WorkoutRow
                  key={w.id}
                  workout={w}
                  isInteractive={weekIdx === 0}
                  isExpanded={!!expandedWorkouts[`${week}-${w.id}`]}
                  onToggle={() =>
                    setExpandedWorkouts((prev) => ({
                      ...prev,
                      [`${week}-${w.id}`]: !prev[`${week}-${w.id}`],
                    }))
                  }
                />
              ))}
          </div>
        </div>
      ))}
      </div>
    </AuthGuard>
  );
}

type WorkoutRowProps = {
  workout: Workout;
  isInteractive: boolean;
  isExpanded: boolean;
  onToggle: () => void;
};

const WorkoutRow: React.FC<WorkoutRowProps> = ({
  workout,
  isInteractive,
  isExpanded,
  onToggle,
}) => {
  const { unitSystem } = useUnitSystem();

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!isInteractive) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onToggle();
    }
  };

  const interactiveClasses = isInteractive
    ? `transition-colors ${isExpanded ? "bg-blue-50" : "hover:bg-blue-50"} cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400`
    : "";

  return (
    <div
      className={`border rounded-lg p-4 bg-white shadow-sm ${interactiveClasses}`}
      onClick={isInteractive ? onToggle : undefined}
      onKeyDown={handleKeyDown}
      role={isInteractive ? "button" : undefined}
      tabIndex={isInteractive ? 0 : undefined}
      aria-expanded={isInteractive ? isExpanded : undefined}
    >
                  <p className="font-medium">
        {format(parseISO(workout.date), "EEE, MMM d")} — {workout.workout_type} (
        {formatDistanceNumber(workout.miles, unitSystem)} {unitSystem === 'metric' ? 'km' : 'mi'})
                  </p>
      {(!isInteractive || isExpanded) && workout.target_zone && (
                    <p className="text-sm text-blue-700 font-medium mt-1">
          Target pace: {parseAndConvertPaceString(workout.target_zone, unitSystem)}
                    </p>
                  )}
      {/* Only show description when no structured notes exist */}
      {(!workout.segments || !workout.segments.notes) && workout.description && (
        <p className="text-sm text-gray-600 mt-2">{workout.description}</p>
      )}

      {/* Show workout segments if available */}
      {(!isInteractive || isExpanded) &&
        workout.segments &&
        workout.segments.steps &&
        Array.isArray(workout.segments.steps) && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-xs font-semibold text-gray-700 mb-2">Workout Structure:</p>
                      <div className="space-y-1">
          {workout.segments.steps.map((step: any, idx: number) => {
                            const formattedDistance = step.durationType === 'DISTANCE'
                              ? formatDistanceNumber(step.value, unitSystem) + (unitSystem === 'metric' ? ' km' : ' mi')
                              : `${step.value} ${step.value === 1 ? 'minute' : 'minutes'}`;

                            return (
                          <div key={idx} className="flex justify-between items-start text-xs">
                            <span className="text-gray-700">
                              {step.name} ({formattedDistance})
                            </span>
                            {step.intensity && (
                              <span className="ml-2 px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                                {step.intensity}
                              </span>
                            )}
                          </div>
                        );
                          })}
                      </div>
          {workout.segments.notes && (
            <p className="text-xs text-gray-600 mt-2 italic">{workout.segments.notes}</p>
                      )}
                    </div>
                  )}
    </div>
  );
};
