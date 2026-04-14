// frontend/src/pages/NewPlanFormV2.tsx
//
// Experimental plan form that targets the refactored /api/plan-v2 pipeline.
// The UI intentionally mirrors the existing NewPlanForm so runners can
// A/B compare outputs while keeping the original path untouched.

import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
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
import { useUnitSystem } from "@/context/UnitSystemContext";
import { formatDistance, getUnitLabels } from "@/utils/unitFormatters";

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
  const location = useLocation();
  const { unitSystem } = useUnitSystem();
  const unitLabels = getUnitLabels(unitSystem);

  // Check if we have saved form data from Back navigation
  const savedFormData = (location.state as any)?.savedFormData;

  const methods = useForm<PlanFormData>({
    resolver: zodResolver(planSchema) as Resolver<PlanFormData>,
    mode: "onChange",  // Real-time validation
    defaultValues: savedFormData ? {
      race_distance: savedFormData.race_distance || "Marathon",
      race_date: savedFormData.race_date || "",
      race_name: savedFormData.race_name || "",
      race_location: savedFormData.race_location || "",
      primary_goal: savedFormData.primary_goal || ("" as any),
      training_days: savedFormData.training_days || [],
      notes: savedFormData.notes || "",
      plan_name: savedFormData.plan_name || "",
    } : {
      race_distance: "Marathon",
      primary_goal: "" as any,
      training_days: [],
      notes: "",
      plan_name: "",
    },
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showErrorModal, setShowErrorModal] = useState(false);
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
      // Check specifically for training days error
      const trainingDaysError = methods.formState.errors.training_days?.message;
      if (trainingDaysError) {
        setError(trainingDaysError);
      } else {
        setError("Please fix the errors below");
      }
      setShowErrorModal(true);
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
      setShowErrorModal(true);
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

  const selectedGoal = methods.watch("primary_goal");
  const selectedDays = methods.watch("training_days") || [];
  const daysCount = selectedDays.length;
  const isDaysValid = daysCount >= 3 && daysCount <= 6;
  const isSixDayPlan = daysCount === 6;

  return (
    <AuthGuard>
      {/* Error Modal */}
      {showErrorModal && error && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md mx-4 transform transition-all">
            <div className="flex items-center mb-4">
              <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center mr-3">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Training Days Required</h3>
            </div>
            <p className="text-gray-600 mb-6">{error}</p>
            <p className="text-sm text-gray-500 mb-6">
              Currently selected: <span className="font-semibold">{daysCount} day{daysCount !== 1 ? 's' : ''}</span>
            </p>
            <button
              onClick={() => setShowErrorModal(false)}
              className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
            >
              Update Training Days
            </button>
          </div>
        </div>
      )}

      {raceDateValidation && (
        <RaceDateValidationDialog
          validation={raceDateValidation}
          onProceed={handleValidationProceed}
          onCancel={handleValidationCancel}
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
                <h1 className="text-3xl font-bold text-gray-800">
                  Generate New Training Plan
                </h1>
              </div>

              {/* Error shown in modal instead of inline banner */}

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
                          {formatDistance(stravaData.recent_weekly_mileage, unitSystem, 1)}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-600">Longest Run</div>
                        <div className="text-lg font-bold text-indigo-900">
                          {formatDistance(stravaData.longest_recent_run, unitSystem, 1)}
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

              {/* Plan Name Section */}
              <div className="space-y-6">
                <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">
                  Plan Name
                </h2>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Plan Name <span className="text-gray-400">(optional)</span>
                  </label>
                  <input
                    type="text"
                    {...methods.register("plan_name")}
                    placeholder="e.g., Chicago Marathon - 4 day plan"
                    maxLength={50}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                  <div className="flex justify-between mt-1">
                    <p className="text-gray-500 text-xs">
                      This name will appear in your plan list
                    </p>
                    <p className={`text-xs ${(methods.watch("plan_name")?.length || 0) > 45 ? 'text-amber-600' : 'text-gray-400'}`}>
                      {methods.watch("plan_name")?.length || 0}/50
                    </p>
                  </div>
                  {methods.formState.errors.plan_name && (
                    <p className="text-red-500 text-sm mt-1">
                      {methods.formState.errors.plan_name.message}
                    </p>
                  )}
                </div>
              </div>

              {/* Race Details */}
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
                      <option value="Marathon">
                        Marathon ({unitSystem === 'metric' ? '42.2' : '26.2'} {unitLabels.distanceAbbrev})
                      </option>
                      <option value="Half Marathon">
                        Half Marathon ({unitSystem === 'metric' ? '21.1' : '13.1'} {unitLabels.distanceAbbrev})
                      </option>
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
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Training Days * <span className="text-gray-400">(select 3, 4, 5, or 6 days)</span>
                  </label>
                  {/* Days counter badge */}
                  <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium mb-3 ${
                    isDaysValid
                      ? 'bg-green-100 text-green-800'
                      : daysCount > 0
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-gray-100 text-gray-600'
                  }`}>
                    {daysCount} day{daysCount !== 1 ? 's' : ''} selected
                    {isDaysValid && (
                      <svg className="w-4 h-4 ml-1" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                    {!isDaysValid && daysCount > 0 && (
                      <span className="ml-1">({daysCount < 3 ? `need ${3 - daysCount} more` : `remove ${daysCount - 6}`})</span>
                    )}
                  </div>
                  {/* Warning banner for 6-day plan */}
                  {isSixDayPlan && (
                    <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                      <div className="flex items-start">
                        <svg className="w-5 h-5 text-amber-600 mt-0.5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                        <div className="flex-1">
                          <h3 className="text-sm font-semibold text-amber-900 mb-1">Advanced Schedule</h3>
                          <p className="text-sm text-amber-800 leading-relaxed">
                            For experienced runners only. Recommended: 35+ mpw, 5+ days/week currently, 2+ years experience.
                            <br />
                            <span className="font-medium">Always include 1 rest day. Keep most runs easy (1-2 hard sessions max). Monitor for overtraining.</span>
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
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

                {/* Long Run Day Selection */}
                <div className="mt-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Long Run Day <span className="text-gray-400">(optional - defaults to Saturday or Sunday)</span>
                  </label>
                  <select
                    {...methods.register("long_run_day")}
                    className="w-full md:w-1/3 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                    disabled={!isDaysValid || daysCount === 0}
                  >
                    <option value="">Auto-select (Saturday/Sunday)</option>
                    {methods.watch("training_days")?.map((day) => {
                      const dayOption = trainingDaysOptions.find(opt => opt.value === day);
                      return (
                        <option key={day} value={day}>
                          {dayOption?.label || day}
                        </option>
                      );
                    })}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Select which day of the week you want your long runs. If not specified, defaults to Saturday if available, otherwise Sunday.
                  </p>
                  {methods.formState.errors.long_run_day && (
                    <p className="text-red-500 text-sm mt-1">
                      {methods.formState.errors.long_run_day.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="hidden">
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
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? "Generating…" : "Generate Plan"}
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
