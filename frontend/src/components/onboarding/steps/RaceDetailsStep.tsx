import { useFormContext } from 'react-hook-form';
import { OnboardingFormData } from '../../../schemas/onboardingSchema';
import { Distances, DistanceLabels } from '../../../schemas/onboardingSchema';

export default function RaceDetailsStep() {
  const { register, formState: { errors } } = useFormContext<OnboardingFormData>();

  return (
    <div className="space-y-6">
      <div>
        <label className="block font-semibold mb-2">When is your marathon?</label>
        <input
          type="date"
          {...register('raceDate')}
          className="w-full border p-2 rounded"
        />
        {errors.raceDate && (
          <p className="text-red-500 text-sm mt-1">{errors.raceDate.message}</p>
        )}
      </div>

      <div>
        <label className="block font-semibold mb-2">Race distance:</label>
        <select
          {...register('raceDistance')}
          className="w-full border p-2 rounded"
          defaultValue="Marathon"
        >
          <option value="">Select distance</option>
          {Distances.map((distance) => (
            <option key={distance} value={distance}>
              {DistanceLabels[distance]}
            </option>
          ))}
        </select>
        {errors.raceDistance && (
          <p className="text-red-500 text-sm mt-1">{errors.raceDistance.message}</p>
        )}
      </div>

      <div>
        <label className="block font-semibold mb-2">Race name (optional):</label>
        <input
          type="text"
          placeholder="e.g., Boston Marathon"
          {...register('raceName')}
          className="w-full border p-2 rounded"
        />
        {errors.raceName && (
          <p className="text-red-500 text-sm mt-1">{errors.raceName.message}</p>
        )}
      </div>

      <div>
        <label className="block font-semibold mb-2">Race location (optional):</label>
        <input
          type="text"
          placeholder="e.g., Boston, MA"
          {...register('raceLocation')}
          className="w-full border p-2 rounded"
        />
        {errors.raceLocation && (
          <p className="text-red-500 text-sm mt-1">{errors.raceLocation.message}</p>
        )}
      </div>
    </div>
  );
}
