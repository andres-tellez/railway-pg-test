// frontend/src/pages/NewPlanForm.tsx

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm, FormProvider, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { planSchema, PlanFormData, trainingDaysOptions, primaryGoalOptions, marathonExperienceOptions } from "@/schemas/planSchema";
import { useApiClient } from "@/utils/apiClient";
import { useAuthSetup } from "@/hooks/useAuthSetup";
import { AuthGuard } from "@/components/AuthGuard";

const NewPlanForm: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();

  const methods = useForm<PlanFormData>({
    resolver: zodResolver(planSchema),
    mode: "onBlur",
    defaultValues: {
      race_distance: "Marathon",
      primary_goal: "" as any, // No default
      marathon_experience: "" as any, // No default
      training_days: [], // No pre-selected days
      notes: "",
    },
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stravaData, setStravaData] = useState<{
    recent_weekly_mileage: number;
    longest_recent_run: number;
    base_level: string;
  } | null>(null);
  const [loadingStrava, setLoadingStrava] = useState(true);

  // Fetch Strava data from API
  useEffect(() => {
    if (!isReady || !userId) return;

    const fetchStravaData = async () => {
      try {
        setLoadingStrava(true);
        // Fetch recent activities to calculate weekly mileage and longest run
        const response = await api.get("/api/activities/");

        // Calculate last complete week's mileage (previous Monday to Sunday)
        const now = new Date();
        const dayOfWeek = now.getDay(); // 0 = Sunday, 1 = Monday, etc.

        // Calculate Monday of the most recent complete week
        const lastSunday = new Date(now);
        lastSunday.setDate(now.getDate() - dayOfWeek); // Last Sunday
        lastSunday.setHours(23, 59, 59, 999); // End of Sunday

        const lastMonday = new Date(lastSunday);
        lastMonday.setDate(lastSunday.getDate() - 6); // Monday of that week
        lastMonday.setHours(0, 0, 0, 0); // Start of Monday

        const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

        console.log("📊 Activity Data Debug:");
        console.log("- Last complete week (Mon-Sun):", lastMonday.toISOString().split('T')[0], "to", lastSunday.toISOString().split('T')[0]);
        console.log("- Total activities received:", response.data?.activities?.length || 0);

        // Get activities from last complete week (Monday to Sunday)
        const lastWeekActivities = response.data?.activities?.filter((act: any) => {
          const actDate = new Date(act.date);
          const inRange = actDate >= lastMonday && actDate <= lastSunday;
          if (inRange) {
            console.log(`  ✓ Activity on ${act.date}: ${act.distance_miles} miles`);
          }
          return inRange;
        }) || [];

        console.log(`- Last week activities: ${lastWeekActivities.length}`);

        const weeklyMileage = lastWeekActivities.reduce((sum: number, act: any) =>
          sum + (act.distance_miles || 0), 0
        );

        console.log(`- Weekly mileage calculated: ${weeklyMileage} miles`);

        // Get longest run from last 30 days (not all-time)
        const activitiesLast30Days = response.data?.activities?.filter((act: any) =>
          new Date(act.date) >= thirtyDaysAgo
        ) || [];
        const longestRun = Math.max(...activitiesLast30Days.map((act: any) => act.distance_miles || 0), 0);

        // Determine base level based on weekly mileage
        let baseLevel = "Unknown";
        if (weeklyMileage > 0 && weeklyMileage < 10) {
          baseLevel = "Low";
        } else if (weeklyMileage >= 10 && weeklyMileage < 25) {
          baseLevel = "Moderate";
        } else if (weeklyMileage >= 25 && weeklyMileage < 40) {
          baseLevel = "Good";
        } else if (weeklyMileage >= 40) {
          baseLevel = "Excellent";
        }

        setStravaData({
          recent_weekly_mileage: Math.round(weeklyMileage * 10) / 10,
          longest_recent_run: Math.round(longestRun * 10) / 10,
          base_level: baseLevel,
        });
      } catch (err) {
        console.error("Error fetching Strava data:", err);
        // Set to "no data" state
        setStravaData({
          recent_weekly_mileage: 0,
          longest_recent_run: 0,
          base_level: "No data",
        });
      } finally {
        setLoadingStrava(false);
      }
    };

    fetchStravaData();
  }, [isReady, userId, api]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Validate all fields
    const isValid = await methods.trigger();
    if (!isValid) {
      setError("Please fix the errors below");
      setLoading(false);
      return;
    }

    try {
      const values = methods.getValues();

      if (!userId) throw new Error("No user ID available - please refresh");

      // Generate a draft (no save)
      const draftRes = await api.post("/api/plan/draft", {
        ...values,
        race_date: values.race_date.split("T")[0],
      });

      // Navigate to draft preview with data in state
      navigate("/plan/draft", {
        replace: false,
        state: {
          draft: draftRes.data?.draft,
          plan_request: {
            ...values,
            race_date: values.race_date.split("T")[0],
          },
        },
      });
    } catch (e: any) {
      const msg =
        e.response?.data?.error ||
        e.response?.data?.message ||
        "Failed to create training plan";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const selectedGoal = methods.watch("primary_goal");

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-3xl mx-auto px-4">
          <FormProvider {...methods}>
            <form onSubmit={handleSubmit} className="bg-white shadow-xl rounded-xl p-8 space-y-8">
              {/* Header */}
              <div className="space-y-2 text-center border-b pb-6">
                <h1 className="text-3xl font-bold text-gray-800">Create New Training Plan</h1>
                <p className="text-gray-600 text-sm">
                  Tell us about your race and goals to generate your personalized training plan
                </p>
              </div>

              {error && (
                <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                  {error}
                </div>
              )}

              {/* Strava Data Display (if available) */}
              {loadingStrava ? (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <div className="text-center text-gray-600">Loading your recent activity...</div>
                </div>
              ) : stravaData && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h3 className="font-semibold text-blue-900 mb-2">Your Recent Activity</h3>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <div className="text-gray-600">Weekly Mileage</div>
                      <div className="text-lg font-bold text-blue-900">
                        {stravaData.recent_weekly_mileage} miles
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-600">Longest Run</div>
                      <div className="text-lg font-bold text-blue-900">
                        {stravaData.longest_recent_run} miles
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-600">Base Level</div>
                      <div className="text-lg font-bold text-blue-900">{stravaData.base_level}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Race Details */}
              <div className="space-y-6">
                <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">
                  Race Details
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Race Date */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Race Date *
                    </label>
                    <input
                      type="date"
                      {...methods.register("race_date")}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    {methods.formState.errors.race_date && (
                      <p className="text-red-500 text-sm mt-1">
                        {methods.formState.errors.race_date.message}
                      </p>
                    )}
                  </div>

                  {/* Race Distance */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Race Distance *
                    </label>
                    <select
                      {...methods.register("race_distance")}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="Marathon">Marathon (26.2 miles)</option>
                      <option value="Half Marathon">Half Marathon (13.1 miles)</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>

                  {/* Race Name (optional) */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Race Name <span className="text-gray-400">(optional)</span>
                    </label>
                    <input
                      type="text"
                      {...methods.register("race_name")}
                      placeholder="e.g., Chicago Marathon"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>

                  {/* Race Location (optional) */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Race Location <span className="text-gray-400">(optional)</span>
                    </label>
                    <input
                      type="text"
                      {...methods.register("race_location")}
                      placeholder="e.g., Chicago, IL"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </div>
              </div>

              {/* Training Goals */}
              <div className="space-y-6">
                <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">
                  Training Goals
                </h2>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Primary Goal *
                  </label>
                  <div className="space-y-3">
                    {primaryGoalOptions.map((option) => (
                      <label key={option.value} className="flex items-center space-x-3 cursor-pointer">
                        <input
                          type="radio"
                          value={option.value}
                          {...methods.register("primary_goal")}
                          className="w-4 h-4 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-gray-700">{option.label}</span>
                      </label>
                    ))}
                  </div>
                  {methods.formState.errors.primary_goal && (
                    <p className="text-red-500 text-sm mt-1">
                      {methods.formState.errors.primary_goal.message}
                    </p>
                  )}
                </div>

                {/* Target Time (conditional) */}
                {selectedGoal === "Target Time" && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Target Time (e.g., 4:30:00) *
                    </label>
                    <input
                      type="text"
                      {...methods.register("target_time")}
                      placeholder="HH:MM:SS"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    {methods.formState.errors.target_time && (
                      <p className="text-red-500 text-sm mt-1">
                        {methods.formState.errors.target_time.message}
                      </p>
                    )}
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Marathon Experience *
                  </label>
                  <div className="space-y-3">
                    {marathonExperienceOptions.map((option) => (
                      <label key={option.value} className="flex items-center space-x-3 cursor-pointer">
                        <input
                          type="radio"
                          value={option.value}
                          {...methods.register("marathon_experience")}
                          className="w-4 h-4 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-gray-700">{option.label}</span>
                      </label>
                    ))}
                  </div>
                  {methods.formState.errors.marathon_experience && (
                    <p className="text-red-500 text-sm mt-1">
                      {methods.formState.errors.marathon_experience.message}
                    </p>
                  )}
                </div>
              </div>

              {/* Training Schedule */}
              <div className="space-y-6">
                <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">
                  Training Schedule
                </h2>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Training Days * <span className="text-gray-400">(select all that apply)</span>
                  </label>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {trainingDaysOptions.map((option) => (
                      <label key={option.value} className="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="checkbox"
                          value={option.value}
                          checked={methods.watch("training_days")?.includes(option.value) || false}
                          onChange={(e) => {
                            const currentDays = methods.getValues("training_days") || [];
                            if (e.target.checked) {
                              methods.setValue("training_days", [...currentDays, option.value]);
                            } else {
                              methods.setValue(
                                "training_days",
                                currentDays.filter((day) => day !== option.value)
                              );
                            }
                          }}
                          className="w-4 h-4 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-gray-700">{option.label}</span>
                      </label>
                    ))}
                  </div>
                  {methods.formState.errors.training_days && (
                    <p className="text-red-500 text-sm mt-1">
                      {methods.formState.errors.training_days.message}
                    </p>
                  )}
                </div>
              </div>

              {/* Additional Notes */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Additional Notes <span className="text-gray-400">(optional)</span>
                </label>
                <textarea
                  {...methods.register("notes")}
                  rows={3}
                  placeholder="Any specific goals, constraints, or information that might help generate a better training plan..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              {/* Submit Button */}
              <div className="flex justify-end space-x-4">
                <button
                  type="button"
                  onClick={() => navigate("/plan/overview")}
                  className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? "Creating..." : "Generate Training Plan"}
                </button>
              </div>
            </form>
          </FormProvider>
        </div>
      </div>
    </AuthGuard>
  );
};

export default NewPlanForm;
