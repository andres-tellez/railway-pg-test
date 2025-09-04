// src/pages/OnboardingForm.tsx
import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { useForm, FormProvider } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { onboardingSchema, OnboardingFormData } from "@/schemas/onboardingSchema";
import { useApiClient } from "@/utils/apiClient";
import RaceGoalStep from "@/components/onboarding/steps/RaceGoalStep";
import TrainingDaysStep from "@/components/onboarding/steps/TrainingDaysStep";
import PhysicalStatsStep from "@/components/onboarding/steps/PhysicalStatsStep";
import RunPreferencesStep from "@/components/onboarding/steps/RunPreferencesStep";
import RunnerLevelStep from "@/components/onboarding/steps/RunnerLevelStep";

const steps = [
  { title: "Runner Level", Component: RunnerLevelStep },
  { title: "Goals", Component: RaceGoalStep },
  { title: "Preferences", Component: RunPreferencesStep },
  { title: "Training Days", Component: TrainingDaysStep },
  { title: "Physical Stats", Component: PhysicalStatsStep },
];

const OnboardingForm: React.FC = () => {
  const { isAuthenticated } = useAuth0();
  const api = useApiClient();
  const navigate = useNavigate();
  const ran = useRef(false);

  const methods = useForm<OnboardingFormData>({
    resolver: zodResolver(onboardingSchema),
    mode: "onBlur",
  });

  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Remove rogue autofill text artifacts
  useEffect(() => {
    const f = document.querySelector("form");
    if (f) {
      Array.from(f.childNodes).forEach((n) => {
        if (n.nodeType === Node.TEXT_NODE && n.textContent?.includes("canceled")) f.removeChild(n);
      });
    }
  }, []);

  // Preload onboarding state if user already submitted it
  useEffect(() => {
    if (!isAuthenticated || ran.current) return;
    ran.current = true;

    const ac = new AbortController();
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get("/onboarding", { signal: ac.signal }); // ✅ fixed path
        if (data) {
          methods.reset(data);
          navigate("/dashboard", { replace: true });
        }
      } catch (e: any) {
        if (e.name !== "AbortError") setError(e.message || "Failed to fetch onboarding data");
      } finally {
        setLoading(false);
      }
    })();
    return () => ac.abort();
  }, [isAuthenticated, api, methods, navigate]);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      const values = methods.getValues();
      await api.post("/onboarding", values); // ✅ fixed path
      navigate("/dashboard", { replace: true });
    } catch (e: any) {
      const msg =
        e.response?.data?.message ||
        JSON.stringify(e.response?.data?.errors) ||
        "Submit error";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleNext = async () => {
    const stepFields: Record<number, (keyof OnboardingFormData)[]> = {
      0: ["runnerLevel"],
      1: ["mainGoal", "motivation"],
      2: ["runPreference"],
      3: ["trainingDays"],
      4: ["height", "weight", "ageGroup"],
    };

    const fields = stepFields[step] || [];
    const valid = await methods.trigger(fields as any);
    if (!valid) return;

    if (step < steps.length - 1) setStep(step + 1);
    else handleSubmit();
  };

  const StepComponent = steps[step].Component;

  if (!isAuthenticated)
    return <div className="p-6 text-red-600 text-center">❌ Not Authenticated</div>;
  if (loading)
    return <div className="p-8 text-center text-gray-600">⏳ Loading onboarding…</div>;

  return (
    <FormProvider {...methods}>
      <form
        className="max-w-2xl mx-auto mt-10 bg-white shadow-xl rounded-xl p-8 space-y-6 border"
        onSubmit={(e) => e.preventDefault()}
      >
        <div className="space-y-1 text-center">
          <h1 className="text-3xl font-bold text-gray-800">Onboarding</h1>
          <p className="text-gray-500 text-sm">
            Step {step + 1} of {steps.length}: {steps[step].title}
          </p>
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <StepComponent />
        </div>

        <div className="flex justify-between pt-6">
          {step > 0 ? (
            <button
              type="button"
              onClick={() => setStep(step - 1)}
              className="px-5 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-100 transition"
              disabled={saving}
            >
              ← Back
            </button>
          ) : (
            <div />
          )}

          <button
            type="button"
            onClick={handleNext}
            disabled={saving}
            className={`px-6 py-2 font-semibold text-white rounded ${
              saving
                ? "bg-blue-300 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700 transition"
            }`}
          >
            {step === steps.length - 1 ? "Finish" : "Next →"}
          </button>
        </div>
      </form>
    </FormProvider>
  );
};

export default OnboardingForm;
