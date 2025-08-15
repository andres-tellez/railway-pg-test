import { useFormContext } from 'react-hook-form';
import type { OnboardingFormData } from '../../../schemas/onboardingSchema';

const weekDays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;

export default function TrainingDaysStep() {
  const { register, formState: { errors }, watch } = useFormContext<OnboardingFormData>();
  const selectedDays = watch('trainingDays') || [];

  return (
    <div className="space-y-4">
      <label className="block font-semibold">Which days would you prefer to train?</label>

      <div className="flex flex-wrap gap-4">
        {weekDays.map((day) => (
          <label key={day} className="inline-flex items-center gap-2">
            <input type="checkbox" value={day} {...register('trainingDays')} />
            {day}
          </label>
        ))}
      </div>

      {errors.trainingDays && (
        <p className="text-red-600 text-sm">Select at least one day.</p>
      )}
    </div>
  );
}
