import { useFormContext } from 'react-hook-form';
import { OnboardingFormData } from '../../../schemas/onboardingSchema';

type Props = {
  formData: Partial<OnboardingFormData>;
  updateFields: (fields: Partial<OnboardingFormData>) => void;
};

export default function RunPreferencesStep({}: Props) {
  const { register } = useFormContext<OnboardingFormData>();

  return (
    <div className="space-y-6">
      <div>
        <label className="block font-semibold">Do you prefer running based on:</label>
        <select
          {...register('runPreference')} // camelCase
          className="border p-2 w-full rounded"
        >
          <option value="">Select preference</option>
          <option value="Distance">Distance</option>
          <option value="Time">Time</option>
          <option value="No preference">No preference</option>
        </select>
      </div>

      <div>
        <label className="block font-semibold">Do you have a target race date?</label>
        <input
          type="date"
          {...register('raceDate')} // camelCase
          className="border p-2 w-full rounded"
        />
      </div>

      <div>
        <label className="block font-semibold">Race distance you're training for:</label>
        <select
          {...register('raceDistance')} // camelCase
          className="border p-2 w-full rounded"
        >
          <option value="">Select distance</option>
          <option value="5K">5K</option>
          <option value="10K">10K</option>
          <option value="Half Marathon">Half Marathon</option>
          <option value="Marathon">Marathon</option>
          <option value="Ultra">Ultra</option>
          <option value="Other">Other</option>
        </select>
      </div>
    </div>
  );
}
