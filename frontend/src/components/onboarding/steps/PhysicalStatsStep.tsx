import { useFormContext } from 'react-hook-form';
import { OnboardingFormData } from '../../../schemas/onboardingSchema';
import { AgeGroups, AgeGroupLabels } from '../../../schemas/onboardingSchema';

export default function PhysicalStatsStep() {
  const { register, formState: { errors } } = useFormContext<OnboardingFormData>();

  return (
    <div className="space-y-6">
      <div>
        <label className="block font-semibold mb-2">Your age group:</label>
        <select
          {...register('ageGroup')}
          className="w-full border p-2 rounded"
        >
          <option value="">Select age group</option>
          {AgeGroups.map((ageGroup) => (
            <option key={ageGroup} value={ageGroup}>
              {AgeGroupLabels[ageGroup]}
            </option>
          ))}
        </select>
        {errors.ageGroup && (
          <p className="text-red-500 text-sm mt-1">{errors.ageGroup.message}</p>
        )}
      </div>

      <div>
        <label className="block font-semibold mb-2">Your height:</label>
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
        {errors.height && (
          <p className="text-red-500 text-sm mt-1">{errors.height.message}</p>
        )}
      </div>

      <div>
        <label className="block font-semibold mb-2">Your weight (lbs):</label>
        <input
          type="number"
          min={80}
          max={400}
          step={1}
          {...register('weight', { valueAsNumber: true })}
          className="w-full border p-2 rounded"
        />
        <p className="text-sm text-gray-600 mt-1">
          Optional - helps us provide more personalized recommendations
        </p>
        {errors.weight && (
          <p className="text-red-500 text-sm mt-1">{errors.weight.message}</p>
        )}
      </div>
    </div>
  );
}
