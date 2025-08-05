import { useFormContext } from 'react-hook-form';
import { OnboardingFormData } from '../../../schemas/onboardingSchema';

const weekDays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;

export default function TrainingDaysStep() {
  const { register, watch } = useFormContext<OnboardingFormData>();
  const selectedDays = watch('trainingDays') || [];

  return (
    <div className="space-y-6">
      <div>
        <label className="block font-semibold">Which days would you prefer to train?</label>
        <div className="flex flex-wrap gap-4 mt-2">
          {weekDays.map((day) => (
            <label key={day} className="flex items-center gap-2">
              <input
                type="checkbox"
                value={day}
                {...register('trainingDays')}
                checked={selectedDays.includes(day)}
              />
              {day}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
