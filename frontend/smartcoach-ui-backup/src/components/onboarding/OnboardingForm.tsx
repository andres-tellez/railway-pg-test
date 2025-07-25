import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { onboardingSchema, OnboardingFormData } from '../../schemas/onboardingSchema';




import RunnerLevelStep from './steps/RunnerLevelStep';

const steps = [RunnerLevelStep];

export default function OnboardingForm() {
  const [stepIndex, setStepIndex] = useState(0);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<OnboardingFormData>({
    resolver: zodResolver(onboardingSchema),
    mode: 'onBlur',
    defaultValues: {} as Partial<OnboardingFormData>, // ✅ key fix
  });

  const onSubmit = (data: OnboardingFormData) => {
    console.log('Complete form data:', data);
  };

  const Step = steps[stepIndex];

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 p-4">
      <Step
        formData={watch()}
        updateFields={(fields: Partial<OnboardingFormData>) => {
          (Object.keys(fields) as (keyof OnboardingFormData)[]).forEach((key) => {
            setValue(key, fields[key]!); // ✅ fixes TS squiggle by asserting defined
          });
        }}
      />

      <div className="flex justify-between">
        {stepIndex > 0 && (
          <button type="button" onClick={() => setStepIndex(stepIndex - 1)}>
            Back
          </button>
        )}
        {stepIndex < steps.length - 1 ? (
          <button type="button" onClick={() => setStepIndex(stepIndex + 1)}>
            Next
          </button>
        ) : (
          <button type="submit">Finish</button>
        )}
      </div>
    </form>
  );
}
