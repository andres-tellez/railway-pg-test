// frontend/src/pages/NewPlanFormV2.tsx
//
// Experimental plan form that targets the refactored /api/plan-v2 pipeline.
// The UI intentionally mirrors the existing NewPlanForm so runners can
// A/B compare outputs while keeping the original path untouched.

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm, FormProvider, Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import {
  planSchema,
  PlanFormData,
  trainingDaysOptions,
  primaryGoalOptions,
} from "@/schemas/planSchema";
import { useApiClient } from "@/utils/apiClient";
import { useAuthSetup } from "@/hooks/useAuthSetup";
import { AuthGuard } from "@/components/AuthGuard";
import { RaceNameAutocomplete } from "@/components/RaceNameAutocomplete";
import { LocationAutocomplete } from "@/components/LocationAutocomplete";
import RaceDateValidationDialog from "@/components/RaceDateValidationDialog";

const googlePlacesApiKey =
  (
    (import.meta as unknown as {
      env?: { VITE_GOOGLE_PLACES_API_KEY?: string };
    })?.env || {}
  ).VITE_GOOGLE_PLACES_API_KEY;

interface MetricsSummaryResponse {
  weekly_trends?: {
    week: string;
    distance: number;
    runs: number;
    avgPace: string;
  }[];
  longest_runs?: {
    week_start: string;
    distance: number;
  }[];
  fitness_summary?: {
    current_weekly_mileage: number;
    current_long_run: number;
  };
}

const NewPlanFormV2: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();

  const methods = useForm<PlanFormData>({
    resolver: zodResolver(planSchema) as Resolver<PlanFormData>,
    mode: "onBlur",
    defaultValues: {
      race_distance: "Marathon",
      primary_goal: "" as any,
      training_days: [],
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

  useEffect(() => {
    if (!isReady || !userId) return;

    const fetchStravaData = async () => {
      try {
        setLoadingStrava(true);
        const response = await api.get<MetricsSummaryResponse>("/api/metrics/all-metrics");

        // Use pre-calculated fitness values from backend (same source as validation)
        // This ensures consistency and eliminates duplicate calculation logic
        const fitnessSummary = response.data?.fitness_summary;
        const weeklyMileage = fitnessSummary?.current_weekly_mileage ?? 0;
        const recentLongestRun = fitnessSummary?.current_long_run ?? 0;

        let baseLevel = "Unknown";
        if (weeklyMileage > 0 && weeklyMileage < 10) baseLevel = "Low";
        else if (weeklyMileage >= 10 && weeklyMileage < 25) baseLevel = "Moderate";
        else if (weeklyMileage >= 25 && weeklyMileage < 40) baseLevel = "Good";
        else if (weeklyMileage >= 40) baseLevel = "Excellent";

        setStravaData({
          recent_weekly_mileage: weeklyMileage,
          longest_recent_run: recentLongestRun,
          base_level: baseLevel,
        });
      } catch (err) {
        console.error("Error fetching Strava data:", err);
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

  const [raceDateValidation, setRaceDateValidation] = useState<any>(null);
  const [pendingDraftData, setPendingDraftData] = useState<any>(null);
  const [pendingRequestPayload, setPendingRequestPayload] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setRaceDateValidation(null);

    const isValid = await methods.trigger();
    if (!isValid) {
      setError("Please fix the errors below");
      setLoading(false);
      return;
    }

    try {
      const values = methods.getValues();
      if (!userId) throw new Error("No user ID available - please refresh");

      const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const requestPayload = {
        ...values,
        race_date: values.race_date.split("T")[0],
        user_timezone: userTimezone,
      };

      const draftRes = await api.post("/api/plan/draft", requestPayload);
      const draftPayload = draftRes.data?.draft;

      // Check for race date validation results (may be in draft or top-level response)
      const validation = draftRes.data?.race_date_validation ||
                        draftRes.data?.draft?.race_date_validation ||
                        draftPayload?.race_date_validation;

      if (validation) {
        // Store draft data for later use
        setPendingDraftData(draftPayload);
        setPendingRequestPayload(requestPayload);
        setRaceDateValidation(validation);
        setLoading(false);
        return; // Don't navigate yet, show dialog
      }

      if (!draftPayload) {
        throw new Error("Draft response missing payload");
      }

      navigate("/plan/draft", {
        replace: false,
        state: {
          draft: draftPayload,
          plan_request: requestPayload,
        },
      });
    } catch (e: any) {
      const msg =
        e.response?.data?.error ||
        e.response?.data?.message ||
        "Failed to create training plan (v2)";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleValidationProceed = () => {
    if (pendingDraftData && pendingRequestPayload) {
      navigate("/plan/draft", {
        replace: false,
        state: {
          draft: pendingDraftData,
          plan_request: pendingRequestPayload,
        },
      });
    }
    setRaceDateValidation(null);
    setPendingDraftData(null);
    setPendingRequestPayload(null);
  };

  const handleValidationCancel = () => {
    setRaceDateValidation(null);
    setPendingDraftData(null);
    setPendingRequestPayload(null);
  };

  const handleAskGPT = () => {
    // TODO: Navigate to GPT chat interface
    // For now, just close the dialog
    console.log("Navigate to GPT chat - TODO: implement");
    handleValidationCancel();
  };

  const selectedGoal = methods.watch("primary_goal");

  return (
    <AuthGuard>
      {raceDateValidation && (
        <RaceDateValidationDialog
          validation={raceDateValidation}
          onProceed={handleValidationProceed}
          onCancel={handleValidationCancel}
          onAskGPT={handleAskGPT}
        />
      )}
      <div className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-3xl mx-auto px-4">
          <FormProvider {...methods}>
            <form
              onSubmit={handleSubmit}
              className="bg-white shadow-xl rounded-xl p-8 space-y-8 border border-indigo-100"
            >
              <div className="space-y-2 text-center border-b pb-6">
                <p className="text-xs uppercase tracking-widest text-indigo-600 font-semibold">
                  Deterministic Plan Pipeline
                </p>
                <h1 className="text-3xl font-bold text-gray-800">
                  Generate New Training Plan
                </h1>
                <p className="text-gray-600 text-sm">
                  This experience uses the refactored /api/plan/draft endpoint for all plan
                  requests. Provide your race details below to get a personalized preview
                  before saving.
                </p>
              </div>

              {error && (
                <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                  {error}
                </div>
              )}

              {loadingStrava ? (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <div className="text-center text-gray-600">
                    Loading your recent activity…
                  </div>
                </div>
              ) : (
                stravaData && (
                  <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
                    <h3 className="font-semibold text-indigo-900 mb-2">
                      Your Recent Activity
                    </h3>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <div className="text-gray-600">Weekly Mileage</div>
                        <div className="text-lg font-bold text-indigo-900">
                          {stravaData.recent_weekly_mileage} miles
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-600">Longest Run</div>
                        <div className="text-lg font-bold text-indigo-900">
                          {stravaData.longest_recent_run} miles
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-600">Base Level</div>
                        <div className="text-lg font-bold text-indigo-900">
                          {stravaData.base_level}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              )}

              {/* The rest of the form mirrors the original component */}
              <div className="space-y-6">
                <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">
                  Race Details
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Race Date *
                    </label>
                    <input
                      type="date"
                      {...methods.register("race_date")}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                    {methods.formState.errors.race_date && (
                      <p className="text-red-500 text-sm mt-1">
                        {methods.formState.errors.race_date.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Race Distance *
                    </label>
                    <select
                      {...methods.register("race_distance")}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    >
                      <option value="Marathon">Marathon (26.2 miles)</option>
                      <option value="Half Marathon">Half Marathon (13.1 miles)</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Race Name <span className="text-gray-400">(optional)</span>
                    </label>
                    <RaceNameAutocomplete
                      control={methods.control}
                      name="race_name"
                      placeholder="e.g., Chicago Marathon"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      onRaceSelect={(race) => {
                        if (race.location && !methods.getValues("race_location")) {
                          methods.setValue("race_location", race.location);
                        }
                        if (
                          race.terrain ||
                          race.elevation_gain ||
                          race.course_type ||
                          race.race_type ||
                          race.difficulty_rating ||
                          race.typical_weather ||
                          race.qualification_required !== undefined
                        ) {
                          const metadata: any = {};
                          if (race.terrain) metadata.terrain = race.terrain;
                          if (race.elevation_gain !== undefined)
                            metadata.elevation_gain = race.elevation_gain;
                          if (race.course_type) metadata.course_type = race.course_type;
                          if (race.race_type) metadata.race_type = race.race_type;
                          if (race.difficulty_rating !== undefined)
                            metadata.difficulty_rating = race.difficulty_rating;
                          if (race.typical_weather) metadata.typical_weather = race.typical_weather;
                          if (race.qualification_required !== undefined)
                            metadata.qualification_required = race.qualification_required;
                          methods.setValue("race_metadata", metadata);
                        }
                      }}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Race Location <span className="text-gray-400">(optional)</span>
                    </label>
                    <LocationAutocomplete
                      control={methods.control}
                      name="race_location"
                      placeholder="e.g., Chicago, IL"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      apiKey={googlePlacesApiKey}
                    />
                  </div>
                </div>
              </div>

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
                      <label
                        key={option.value}
                        className="flex items-center space-x-3 cursor-pointer"
                      >
                        <input
                          type="radio"
                          value={option.value}
                          {...methods.register("primary_goal")}
                          className="w-4 h-4 text-indigo-600 focus:ring-indigo-500"
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
                {selectedGoal === "Target Time" && (
                  <div className="bg-yellow-50 border border-yellow-300 text-yellow-800 rounded-md p-4">
                    <p className="font-medium">Target Time plans are still in development.</p>
                    <p className="text-sm mt-1">
                      Please select <span className="font-semibold">Just Finish</span> to test the v2
                      generator.
                    </p>
                  </div>
                )}
              </div>

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
                      <label
                        key={option.value}
                        className="flex items-center space-x-2 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          value={option.value}
                          checked={
                            methods.watch("training_days")?.includes(option.value) || false
                          }
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
                          className="w-4 h-4 text-indigo-600 focus:ring-indigo-500"
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

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Additional Notes <span className="text-gray-400">(optional)</span>
                </label>
                <textarea
                  {...methods.register("notes")}
                  rows={3}
                  placeholder="Any specific goals, constraints, or information that might help generate a better training plan..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

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
                  disabled={loading || selectedGoal === "Target Time"}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? "Generating…" : "Generate V2 Draft"}
                </button>
              </div>
            </form>
          </FormProvider>
        </div>
      </div>
    </AuthGuard>
  );
};

export default NewPlanFormV2;
