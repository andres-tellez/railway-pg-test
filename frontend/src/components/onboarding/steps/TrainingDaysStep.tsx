// src/components/OnboardingSteps/TrainingDaysStep.tsx
import { useFormContext, Controller } from "react-hook-form";
import type { OnboardingFormData } from "../../../schemas/onboardingSchema";
import { Days, DayLabels, Motivations, MotivationLabels } from "../../../schemas/onboardingSchema";

export default function TrainingDaysStep() {
  const {
    control,
    watch,
    formState: { errors },
  } = useFormContext<OnboardingFormData>();

  const selectedDays = watch("trainingDays") || [];

  return (
    <div className="space-y-6">
      {/* Training Days */}
      <div>
        <label className="block font-semibold mb-2">Which days can you train?</label>
        <p className="text-sm text-gray-600 mb-4">
          For marathon training, we recommend 3-5 training days per week
        </p>

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
          <p className="text-red-600 text-sm mt-2">{errors.trainingDays.message}</p>
        )}

        {/* Validation warnings */}
        {selectedDays.length > 0 && selectedDays.length < 3 && (
          <div className="mt-2 p-3 bg-yellow-100 border border-yellow-400 text-yellow-700 rounded">
            <p className="text-sm">
              ⚠️ You've selected {selectedDays.length} day{selectedDays.length !== 1 ? 's' : ''}.
              We recommend at least 3 training days per week for marathon preparation.
            </p>
          </div>
        )}

        {selectedDays.length > 5 && (
          <div className="mt-2 p-3 bg-yellow-100 border border-yellow-400 text-yellow-700 rounded">
            <p className="text-sm">
              ⚠️ You've selected {selectedDays.length} days.
              More than 5 training days per week increases injury risk and is not necessary for finishing a marathon.
            </p>
          </div>
        )}

        {selectedDays.length >= 3 && selectedDays.length <= 5 && (
          <div className="mt-2 p-3 bg-green-100 border border-green-400 text-green-700 rounded">
            <p className="text-sm">
              ✅ Great! {selectedDays.length} training days per week is perfect for marathon training.
            </p>
          </div>
        )}
      </div>

      {/* Motivation */}
      <div>
        <label className="block font-semibold mb-2">What motivates you to run? (Select all that apply)</label>
        <p className="text-sm text-gray-600 mb-4">
          This helps us tailor your training plan to your goals
        </p>

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
    </div>
  );
}
