import { useFormContext } from 'react-hook-form';
import { OnboardingFormData } from '../../../schemas/onboardingSchema';

type Props = {
  formData: Partial<OnboardingFormData>;
  updateFields: (fields: Partial<OnboardingFormData>) => void;
};

export default function RunnerLevelStep({ formData }: Props) {
  const { register, watch } = useFormContext<OnboardingFormData>();
  const runnerLevel = watch('runnerLevel'); // ✅ camelCase

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">What's your current running level?</h2>

      <div className="space-y-2">
        {['Beginner', 'Intermediate', 'Expert'].map((level) => (
          <label key={level} className="flex items-center gap-2">
            <input
              type="radio"
              value={level}
              {...register('runnerLevel')} // ✅ camelCase
              checked={runnerLevel === level}
            />
            {level}
          </label>
        ))}
      </div>
    </div>
  );
}
