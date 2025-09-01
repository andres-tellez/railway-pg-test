// src/pages/OnboardingForm.tsx
import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { useForm, FormProvider } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { onboardingSchema, OnboardingFormData } from "@/schemas/onboardingSchema";
import { useApiClient } from "@/utils/apiClient";

// Step components
import RaceGoalStep from "@/components/onboarding/steps/RaceGoalStep";
import TrainingDaysStep from "@/components/onboarding/steps/TrainingDaysStep";
import PhysicalStatsStep from "@/components/onboarding/steps/PhysicalStatsStep";
import RunPreferencesStep from "@/components/onboarding/steps/RunPreferencesStep";
import RunnerLevelStep from "@/components/onboarding/steps/RunnerLevelStep";

const steps = [
  { title: "Goals", Component: RaceGoalStep },
  { title: "Training Days", Component: TrainingDaysStep },
  { title: "Physical Stats", Component: PhysicalStatsStep },
  { title: "Preferences", Component: RunPreferencesStep },
  { title: "Runner Level", Component: RunnerLevelStep },
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

  useEffect(() => {
    if (!isAuthenticated || ran.current) return;
    ran.current = true;

    const ac = new AbortController();
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get("/api/onboarding", {
          signal: ac.signal,
        });

        if (data) {
          methods.reset(data);
          navigate("/dashboard", { replace: true });
        }
      } catch (e: any) {
        if (e?.name !== "AbortError") {
          setError(e.message || "Failed to fetch onboarding data");
        }
      } finally {
        setLoading(false);
      }
    })();
    return () => ac.abort();
  }, [isAuthenticated, api, methods, navigate]);

  const handleBack = () => {
    if (step > 0) setStep(step - 1);
  };

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      const values = methods.getValues();
      await api.post("/api/onboarding", values);
      navigate("/dashboard", { replace: true });
    } catch (e: any) {
      const msg = e?.response?.data?.message || JSON.stringify(e?.response?.data?.errors) || "Submit error";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleNext = async () => {
    const valid = await methods.trigger();
    if (!valid) return;

    if (step < steps.length - 1) setStep(step + 1);
    else handleSubmit();
  };

  const StepComponent = steps[step].Component;
  if (loading) return <div className="p-8">Loading…</div>;

  return (
    <FormProvider {...methods}>
      <form className="p-6 max-w-2xl mx-auto space-y-4" onSubmit={(e) => e.preventDefault()}>
        <h1 className="text-xl font-semibold">{steps[step].title}</h1>

        {error && <div className="text-red-600 bg-red-50 border p-2 rounded">{error}</div>}

        <StepComponent />

        <div className="flex justify-between pt-4">
          {step > 0 && (
            <button
              type="button"
              onClick={handleBack}
              className="px-4 py-2 border rounded"
              disabled={saving}
            >
              Back
            </button>
          )}
          <button
            type="button"
            onClick={handleNext}
            className="px-4 py-2 bg-blue-600 text-white rounded"
            disabled={saving}
          >
            {step === steps.length - 1 ? "Finish" : "Next"}
          </button>
        </div>
      </form>
    </FormProvider>
  );
};

export default OnboardingForm;
