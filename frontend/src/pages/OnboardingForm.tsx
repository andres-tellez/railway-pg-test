// src/pages/OnboardingForm.tsx
import { useForm, FormProvider } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  onboardingSchema,
  type OnboardingFormData,
} from "../schemas/onboardingSchema";
import { useAuthSync } from "../hooks/useAuthSync";

import RunnerLevelStep from "../components/onboarding/steps/RunnerLevelStep";
import RaceGoalStep from "../components/onboarding/steps/RaceGoalStep";
import RunPreferencesStep from "../components/onboarding/steps/RunPreferencesStep";
import RaceHistoryStep from "../components/onboarding/steps/RaceHistoryStep";
import PhysicalStatsStep from "../components/onboarding/steps/PhysicalStatsStep";
import TrainingDaysStep from "../components/onboarding/steps/TrainingDaysStep";
import DevAuthTools from "../components/DevAuthTools";

const steps = [
  { label: "Runner Level", Component: RunnerLevelStep },
  { label: "Goals & Motivation", Component: RaceGoalStep },
  { label: "Run Preferences", Component: RunPreferencesStep },
  { label: "Race History", Component: RaceHistoryStep },
  { label: "Physical Stats", Component: PhysicalStatsStep },
  { label: "Training Days", Component: TrainingDaysStep },
] as const;

type FormKeys = keyof OnboardingFormData;

const requiredFieldsPerStep: Record<number, FormKeys[]> = {
  0: ["runnerLevel"],
  1: ["mainGoal", "motivation"],
  2: ["runPreference"],
  3: ["raceHistory", "pastRaces", "raceDate", "raceDistance"],
  4: ["height", "weight", "ageGroup"],
  5: ["trainingDays"],
};

export default function OnboardingForm() {
  // Auth0 user.sub (string) or null while loading
  const token = useAuthSync();

  const [stepIndex, setStepIndex] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const navigate = useNavigate();

  const urlParams = useMemo(
    () => new URLSearchParams(window.location.search),
    []
  );
  const editMode = urlParams.get("edit") === "true";

  const methods = useForm<OnboardingFormData>({
    resolver: zodResolver(onboardingSchema),
    mode: "onSubmit",
    shouldUnregister: false,
    defaultValues: {
      user_id: "",
      runnerLevel: undefined,
      mainGoal: undefined,
      motivation: [],
      raceHistory: false,
      pastRaces: [],
      raceDate: undefined,
      raceDistance: undefined,
      runPreference: undefined,
      height: undefined,
      weight: undefined,
      ageGroup: undefined,
      trainingDays: [],
    } as unknown as OnboardingFormData,
  });

  const { handleSubmit, setValue, reset, trigger, formState, getValues } = methods;

  // Tiny debug ping (ok if 404s)
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch("/api/onboarding-debug-ping");
        console.debug("[Onboarding] debug ping status:", r.status);
      } catch (e) {
        console.debug("[Onboarding] debug ping failed:", e);
      }
    })();
  }, []);

  // Prefill when editing an existing profile
  useEffect(() => {
    if (!token || !editMode) return;

    (async () => {
      try {
        const res = await fetch(`/api/onboarding?user_id=${encodeURIComponent(token)}`);
        if (!res.ok) {
          console.debug("[Onboarding] prefill GET status:", res.status);
          return;
        }
        const data = await res.json();
        const profile = data?.data;
        if (!profile) return;

        setValue("runnerLevel", profile.runner_level ?? undefined);
        setValue("mainGoal", profile.main_goal ?? "General fitness");
        setValue("motivation", profile.motivation ?? []);
        setValue("raceHistory", !!profile.race_history);
        setValue("pastRaces", profile.past_races ?? []);
        setValue("raceDate", profile.race_date ?? undefined);
        setValue("raceDistance", profile.race_distance ?? undefined);
        setValue("runPreference", profile.run_preference ?? "No preference");
        setValue("height", {
          feet: profile.height_feet ?? 5,
          inches: profile.height_inches ?? 6,
        });
        setValue("weight", profile.weight ?? 150);
        setValue("ageGroup", profile.age_group ?? "25-34");
        setValue("trainingDays", profile.training_days ?? []);
        setValue("user_id", token, {
          shouldValidate: false,
          shouldDirty: false,
          shouldTouch: false,
        });
      } catch (err) {
        console.error("❌ Error loading profile for edit:", err);
      }
    })();
  }, [token, editMode, setValue]);

  // Ensure user_id mirrors Auth0 subject as soon as token is available
  useEffect(() => {
    if (!token) return;
    if (getValues("user_id") !== token) {
      setValue("user_id", token, {
        shouldValidate: false,
        shouldDirty: false,
        shouldTouch: false,
      });
      console.debug("[Onboarding] user_id injected from useAuthSync()");
    }
  }, [token, getValues, setValue]);

  const onSubmit = async (data: OnboardingFormData) => {
    setErrorMessage("");
    console.debug("[Onboarding] onSubmit fired");

    const payload: Record<string, any> = {
      ...data,
      heightFeet: data.height?.feet ?? null,
      heightInches: data.height?.inches ?? null,
      pastRaces: data.pastRaces?.length ? data.pastRaces : ["Haven't raced yet"],
      raceDate: data.raceDate || undefined,
      raceDistance: data.raceDistance || undefined,
      runPreference: data.runPreference || "No preference",
      trainingDays: Array.isArray(data.trainingDays)
        ? data.trainingDays.map((d) => d.trim())
        : [],
    };
    delete payload.height;

    try {
      console.debug("[Onboarding] POST /api/onboarding payload:", payload);
      const res = await fetch("/api/onboarding", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      console.debug("[Onboarding] POST status:", res.status);
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        let parsed: any = {};
        try {
          parsed = JSON.parse(text);
        } catch {
          /* noop */
        }
        console.error("[Onboarding] POST error body:", parsed || text);
        setErrorMessage(parsed?.message || text || "Request failed");
        return;
      }

      reset();
      navigate("/dashboard");
    } catch (err) {
      console.error("❌ Error submitting onboarding:", err);
      setErrorMessage("Unexpected error. Please try again later.");
    }
  };

  const onSubmitError = (errors: unknown) => {
    console.warn("[Onboarding] validation errors:", errors);
    setErrorMessage("Please complete the required fields.");
  };

  const StepComponent = steps[stepIndex].Component;
  const isSubmitting = formState.isSubmitting;

  // 🔒 IMPORTANT: don’t render the form until Auth has finished.
  // This avoids the “stuck on /post-oauth” feel and ensures user_id is ready.
  if (!token) {
    return (
      <>
        <DevAuthTools />
        <div className="max-w-xl mx-auto p-6">Finishing sign-in…</div>
      </>
    );
  }

  return (
    <>
      <DevAuthTools /> {/* dev-only widget; safe to remove later */}

      <FormProvider {...methods}>
        <form
          noValidate
          className="max-w-xl mx-auto p-6 space-y-6"
          onSubmit={handleSubmit(onSubmit, onSubmitError)}
          onKeyDown={(e) => {
            // prevent accidental submits on Enter within multi-step
            if (e.key === "Enter") e.preventDefault();
          }}
        >
          <h2 className="text-2xl font-bold">{steps[stepIndex].label}</h2>

          <StepComponent />

          {errorMessage && (
            <div className="text-red-600 border border-red-400 p-2 rounded bg-red-100">
              {errorMessage}
            </div>
          )}

          <div className="flex justify-between">
            {stepIndex > 0 && (
              <button
                type="button"
                className="px-4 py-2 bg-gray-300 rounded"
                onClick={() => setStepIndex((i) => i - 1)}
              >
                Back
              </button>
            )}

            {stepIndex < steps.length - 1 ? (
              <button
                type="button"
                className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-60"
                disabled={isSubmitting}
                onClick={async () => {
                  const required = requiredFieldsPerStep[stepIndex] || [];
                  const ok = await trigger(required, { shouldFocus: true });
                  if (ok) setStepIndex((i) => i + 1);
                }}
              >
                Next
              </button>
            ) : (
              <button
                type="submit"
                className="px-4 py-2 bg-green-600 text-white rounded disabled:opacity-60"
                disabled={isSubmitting}
                aria-busy={isSubmitting}
                data-testid="onboarding-submit"
              >
                {isSubmitting ? "Submitting…" : "Submit"}
              </button>
            )}
          </div>
        </form>
      </FormProvider>
    </>
  );
}
