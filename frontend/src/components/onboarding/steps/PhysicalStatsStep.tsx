import { useFormContext } from 'react-hook-form';
import { OnboardingFormData } from '../../../schemas/onboardingSchema';

export default function PhysicalStatsStep() {
  const { register } = useFormContext<OnboardingFormData>();

  return (
    <div className="space-y-6">
      <div>
        <label className="block font-semibold">Your height:</label>
        <div className="flex gap-4">
          <input
            type="number"
            min={3}
            max={8}
            placeholder="Feet"
            {...register('height.feet', { valueAsNumber: true })}
            className="border p-2 rounded w-1/3"
          />
          <input
            type="number"
            min={0}
            max={11}
            placeholder="Inches"
            {...register('height.inches', { valueAsNumber: true })}
            className="border p-2 rounded w-1/3"
          />
        </div>
      </div>

      <div>
        <label className="block font-semibold">Your weight (lbs):</label>
        <input
          type="number"
          min={80}
          max={400}
          step={1}
          {...register('weight', { valueAsNumber: true })}
          className="mt-1 border p-2 w-full rounded"
        />
      </div>

      <div>
        <label className="block font-semibold">Your age group:</label>
        <select {...register('ageGroup')} className="mt-1 border p-2 w-full rounded">
          <option value="">Select age group</option>
          <option value="Under 18">Under 18</option>
          <option value="18-24">18-24</option>
          <option value="25-34">25-34</option>
          <option value="35-44">35-44</option>
          <option value="45-54">45-54</option>
          <option value="55+">55+</option>
        </select>
      </div>

      <div>
        <label className="block font-semibold">Longest run ever (miles):</label>
        <input
          type="number"
          min={0}
          step={1}
          {...register('longestRun', {
            setValueAs: (v) => (v === '' ? undefined : parseInt(v, 10)),
            validate: (v) =>
              Number.isInteger(v) || 'Please enter a whole number (no decimals)',
          })}
          className="mt-1 border p-2 w-full rounded"
        />
      </div>
    </div>
  );
}
