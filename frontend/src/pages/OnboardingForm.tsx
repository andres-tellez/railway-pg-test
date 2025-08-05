import { useForm, FormProvider } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { onboardingSchema, OnboardingFormData } from '../schemas/onboardingSchema';
import { useAuthSync } from '../hooks/useAuthSync';
import RunnerLevelStep from '../components/onboarding/steps/RunnerLevelStep';
import RaceGoalStep from '../components/onboarding/steps/RaceGoalStep';
import TrainingDaysStep from '../components/onboarding/steps/TrainingDaysStep';
import InjuryStep from '../components/onboarding/steps/InjuryStep';
import RaceHistoryStep from '../components/onboarding/steps/RaceHistoryStep';
import PhysicalStatsStep from '../components/onboarding/steps/PhysicalStatsStep';
import RunPreferencesStep from '../components/onboarding/steps/RunPreferencesStep';

const steps = [
  { label: 'Runner Level', Component: RunnerLevelStep },
  { label: 'Goals & Motivation', Component: RaceGoalStep },
  { label: 'Run Preferences', Component: RunPreferencesStep },
  { label: 'Race History', Component: RaceHistoryStep },
  { label: 'Physical Stats', Component: PhysicalStatsStep },
  { label: 'Training Days', Component: TrainingDaysStep },
  { label: 'Injury Info', Component: InjuryStep },
];

const requiredFieldsPerStep: Record<number, (keyof OnboardingFormData)[]> = {
  0: ['runnerLevel'],
  1: ['mainGoal', 'motivation'],
  2: ['runPreference'],
  3: ['raceHistory', 'pastRaces', 'raceDate', 'raceDistance'],
  4: ['height', 'weight', 'ageGroup'],
  5: ['trainingDays', 'longestRun'],
  6: ['hasInjury'],
};

const API_BASE_URL = (import.meta.env as any).VITE_API_BASE_URL || 'http://localhost:5000';

export default function OnboardingForm() {
  const token = useAuthSync();
  const [stepIndex, setStepIndex] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const navigate = useNavigate();
  const urlParams = new URLSearchParams(window.location.search);
  const editMode = urlParams.get('edit') === 'true';

  const methods = useForm<OnboardingFormData>({
    resolver: zodResolver(onboardingSchema),
    mode: 'onSubmit',
    defaultValues: {
      user_id: '',
      runnerLevel: undefined,
      mainGoal: '',
      motivation: [],
      raceHistory: undefined,
      pastRaces: [],
      raceDate: undefined,
      raceDistance: '',
      runPreference: '',
      height: { feet: undefined, inches: undefined },
      weight: undefined,
      ageGroup: '',
      trainingDays: [],
      longestRun: undefined,
      hasInjury: null,
      injuryDetails: undefined,
    },
  });

  const { handleSubmit, setValue, watch, reset, trigger, formState, getValues } = methods;

  useEffect(() => {
    if (!token || !editMode) return;

    fetch(`${API_BASE_URL}/api/onboarding?user_id=${token}`)
      .then(res => res.json())
      .then(data => {
        if (data.status === "success" && data.data) {
          const profile = data.data;
          try {
            setValue("runnerLevel", profile.runner_level);
            setValue("mainGoal", profile.main_goal || 'General fitness');
            setValue("motivation", profile.motivation || []);
            setValue("raceHistory", profile.race_history);
            setValue("pastRaces", profile.past_races || []);
            setValue("raceDate", profile.race_date || undefined);
            setValue("raceDistance", profile.race_distance || undefined);
            setValue("runPreference", profile.run_preference || "No preference");
            setValue("height", { feet: profile.height_feet ?? 5, inches: profile.height_inches ?? 6 });
            setValue("weight", profile.weight || 150);
            setValue("ageGroup", profile.age_group || '25-34');
            setValue("trainingDays", profile.training_days || []);
            setValue("longestRun", profile.longest_run || undefined);
            setValue("hasInjury", profile.has_injury === "Yes");
            setValue("injuryDetails", profile.injury_details || undefined);
            setValue("user_id", token);
          } catch (err) {
            console.error("❌ Error setting profile defaults:", err);
          }
        }
      })
      .catch(err => console.error("❌ Error loading profile:", err));
  }, [token, setValue, editMode]);

  useEffect(() => {
    if (token && getValues('user_id') !== token) {
      reset(current => ({ ...current, user_id: token }));
    }
  }, [formState.errors, token, reset]);

  const onSubmit = async (data: OnboardingFormData) => {
    setErrorMessage('');

    const sanitized = {
      ...data,
      heightFeet: data.height?.feet ?? null,
      heightInches: data.height?.inches ?? null,
      pastRaces: data.pastRaces.length > 0 ? data.pastRaces : ["Haven't raced yet"],
      raceDate: data.raceDate || undefined,
      raceDistance: data.raceDistance || undefined,
      runPreference: data.runPreference || "No preference",
      trainingDays: Array.isArray(data.trainingDays) ? data.trainingDays.map(d => d.trim()) : [],
      injuryDetails: data.hasInjury ? data.injuryDetails : undefined,
    };

    delete (sanitized as any).height;

    try {
      const response = await fetch(`${API_BASE_URL}/api/onboarding`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(sanitized),
      });

      if (!response.ok) {
        const error = await response.json();
        setErrorMessage(error.message || JSON.stringify(error));
        return;
      }

      alert('🎉 Onboarding submitted successfully!');
      reset();
      navigate('/dashboard');
    } catch (err) {
      console.error('Error submitting onboarding:', err);
      setErrorMessage('Unexpected error. Please try again later.');
    }
  };

  const StepComponent = steps[stepIndex].Component;

  return (
    <FormProvider {...methods}>
      <form
        onSubmit={handleSubmit(onSubmit)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.preventDefault();
        }}
        className="max-w-xl mx-auto p-6 space-y-6"
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
              onClick={() => setStepIndex(i => i - 1)}
            >
              Back
            </button>
          )}
          {stepIndex < steps.length - 1 ? (
            <button
              type="button"
              className="px-4 py-2 bg-blue-500 text-white rounded"
              onClick={async () => {
                const requiredFields =
                  stepIndex === 6
                    ? ['hasInjury', ...(getValues('hasInjury') === true ? ['injuryDetails'] : [])]
                    : requiredFieldsPerStep[stepIndex];

                const isValid = await trigger(requiredFields);
                if (isValid) setStepIndex(i => i + 1);
              }}
            >
              Next
            </button>
          ) : (
            <button type="submit" className="px-4 py-2 bg-green-500 text-white rounded">
              Submit
            </button>
          )}
        </div>
      </form>
    </FormProvider>
  );
}
