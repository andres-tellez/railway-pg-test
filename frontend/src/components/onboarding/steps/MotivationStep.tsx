// src/components/onboarding/steps/MotivationStep.tsx
import { useFormContext, Controller } from "react-hook-form";
import type { OnboardingFormData } from "../../../schemas/onboardingSchema";
import { Motivations, MotivationLabels } from "../../../schemas/onboardingSchema";

export default function MotivationStep() {
  const {
    control,
    formState: { errors },
  } = useFormContext<OnboardingFormData>();

  return (
    <div>
      <label className="block font-semibold mb-2">What motivates you to run? (Select all that apply)</label>

      <Controller
        name="motivation"
        control={control}
        render={({ field }) => (
          <div className="flex flex-wrap gap-4">
            {Motivations.map((motivation) => (
              <label key={motivation} className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  value={motivation}
                  checked={field.value?.includes(motivation)}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    const value = e.target.value;
                    const newValue = checked
                      ? [...(field.value || []), value]
                      : (field.value || []).filter((v) => v !== value);
                    field.onChange(newValue);
                  }}
                  className="h-5 w-5 text-blue-600 focus:ring-blue-500 border-gray-300 rounded cursor-pointer"
                />
                <span>{MotivationLabels[motivation]}</span>
              </label>
            ))}
          </div>
        )}
      />

      {errors.motivation && (
        <p className="text-red-600 text-sm mt-2">{errors.motivation.message}</p>
      )}
    </div>
  );
}
