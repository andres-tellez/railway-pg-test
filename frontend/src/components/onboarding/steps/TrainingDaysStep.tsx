// src/components/OnboardingSteps/TrainingDaysStep.tsx
import { useFormContext, Controller } from "react-hook-form";
import type { OnboardingFormData } from "../../../schemas/onboardingSchema";
import { Days, DayLabels } from "../../../schemas/onboardingSchema";

export default function TrainingDaysStep() {
  const {
    control,
    watch,
    formState: { errors },
  } = useFormContext<OnboardingFormData>();

  const selectedDays = watch("trainingDays") || [];

  return (
    <div className="space-y-4">
      <label className="block font-semibold">Which days would you prefer to train?</label>

      <Controller
        name="trainingDays"
        control={control}
        render={({ field }) => (
          <div className="flex flex-wrap gap-4">
            {Days.map((day) => (
              <label key={day} className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  value={day}
                  checked={field.value?.includes(day)}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    const value = e.target.value;
                    const newValue = checked
                      ? [...(field.value || []), value]
                      : (field.value || []).filter((v) => v !== value);
                    field.onChange(newValue);
                  }}
                />
                {DayLabels[day]}
              </label>
            ))}
          </div>
        )}
      />

      {errors.trainingDays && (
        <p className="text-red-600 text-sm">{errors.trainingDays.message}</p>
      )}
    </div>
  );
}
