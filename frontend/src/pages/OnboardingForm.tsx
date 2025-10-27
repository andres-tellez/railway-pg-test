// src/pages/OnboardingForm.tsx
import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm, FormProvider } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { onboardingSchema, OnboardingFormData } from "@/schemas/onboardingSchema";
import { useApiClient } from "@/utils/apiClient";
import { useAuthSetup } from "@/hooks/useAuthSetup";
import { AuthGuard } from "@/components/AuthGuard";
import RaceDetailsStep from "@/components/onboarding/steps/RaceDetailsStep";
import TrainingDaysStep from "@/components/onboarding/steps/TrainingDaysStep";
import PhysicalStatsStep from "@/components/onboarding/steps/PhysicalStatsStep";

const OnboardingForm: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();
  const ran = useRef(false);

  const methods = useForm<OnboardingFormData>({
    resolver: zodResolver(onboardingSchema),
    mode: "onBlur",
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Preload profile data if user already submitted it
  useEffect(() => {
    if (!isReady || !userId || ran.current) return;
    ran.current = true;

    const ac = new AbortController();
    (async () => {
      setLoading(true);
      try {
        console.log("Fetching profile data...");
        const { data } = await api.get("api/onboarding", { signal: ac.signal });
        console.log("Received profile data:", data);
        if (data) {
          // Pre-fill the form with existing data (for editing)
          console.log("Resetting form with data...");
          methods.reset(data);
          console.log("Form reset complete");
        } else {
          console.log("No profile data received");
        }
      } catch (e: any) {
        if (e.name !== "AbortError") {
          console.error("Error fetching profile:", e);
          // User doesn't have a profile yet - this is expected for new users
          console.log("No existing profile found - showing empty form");
        }
      } finally {
        setLoading(false);
      }
    })();
    return () => ac.abort();
  }, [isReady, userId, methods, api]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    // Validate all fields
    const isValid = await methods.trigger();
    if (!isValid) {
      setError("Please fix the errors below");
      setSaving(false);
      return;
    }

    try {
      const values = methods.getValues();

      if (!userId) throw new Error("No user ID available - please refresh");

      await api.post("api/onboarding", {
        ...values,
      });

      navigate("/home", { replace: true });
    } catch (e: any) {
      const msg =
        e.response?.data?.message ||
        JSON.stringify(e.response?.data?.errors) ||
        "Failed to save profile";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AuthGuard>
        <div className="p-8 text-center text-gray-600">⏳ Loading profile…</div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <FormProvider {...methods}>
        <form
          onSubmit={handleSubmit}
          className="max-w-2xl mx-auto mt-10 bg-white shadow-xl rounded-xl p-8 space-y-6 border"
        >
          <div className="space-y-1 text-center">
            <h1 className="text-3xl font-bold text-gray-800">User Profile</h1>
            <p className="text-gray-500 text-sm">
              Tell us about yourself to personalize your training plan
            </p>
          </div>

          {error && error !== "canceled" && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div className="space-y-8">
            {/* Physical Stats Section */}
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">
                Physical Stats
              </h2>
              <PhysicalStatsStep />
            </div>

            {/* Training Schedule Section */}
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">
                Training Schedule
              </h2>
              <TrainingDaysStep />
            </div>

            {/* Race Details Section */}
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">
                Race Details (Optional)
              </h2>
              <RaceDetailsStep />
            </div>
          </div>

          <div className="flex justify-end pt-6">
            <button
              type="submit"
              disabled={saving}
              className={`px-8 py-3 font-semibold text-white rounded-lg transition ${
                saving
                  ? "bg-blue-300 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {saving ? "Saving..." : "Save Profile"}
            </button>
          </div>
        </form>
      </FormProvider>
    </AuthGuard>
  );
};

export default OnboardingForm;
