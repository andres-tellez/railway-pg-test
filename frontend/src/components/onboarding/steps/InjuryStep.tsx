import { useFormContext, Controller } from 'react-hook-form';
import { OnboardingFormData } from '../../../schemas/onboardingSchema';

export default function InjuryStep() {
  const {
    control,
    watch,
    register,
    formState: { errors },
  } = useFormContext<OnboardingFormData>();

  const hasInjury = watch('hasInjury');

  return (
    <div className="space-y-6">
      <div>
        <label className="block font-semibold">
          Do you currently have a running injury?
        </label>

        <Controller
          name="hasInjury"
          control={control}
          rules={{ required: 'Please select an option' }}
          render={({ field }) => (
            <div className="flex gap-4 mt-2">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name={field.name}
                  checked={field.value === true}
                  onChange={() => field.onChange(true)}
                />
                Yes
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name={field.name}
                  checked={field.value === false}
                  onChange={() => field.onChange(false)}
                />
                No
              </label>
            </div>
          )}
        />

        {errors.hasInjury && (
          <p className="text-red-500 text-sm mt-1">{errors.hasInjury.message}</p>
        )}
      </div>

      {hasInjury === true && (
        <div>
          <label className="block font-semibold">Please describe your injury:</label>
          <textarea
            {...register('injuryDetails')}
            className="mt-1 border p-2 w-full rounded"
            rows={4}
          />
        </div>
      )}
    </div>
  );
}
