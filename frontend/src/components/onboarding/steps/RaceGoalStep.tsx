import { useFormContext } from "react-hook-form";
import { OnboardingFormData } from "../../../schemas/onboardingSchema";

export default function RaceGoalStep() {
  const {
    watch,
    register,
    formState: { errors },
  } = useFormContext<OnboardingFormData>();

  const selectedMotivation = watch("motivation") || [];

  return (
    <div className="space-y-6">
      {/* Main Goal */}
      <div>
        <label className="block font-semibold mb-1">Main Goal</label>
        <select
        {...register("mainGoal")}
        className="w-full border p-2 rounded"
      >
        <option value="">-- Select your goal --</option>
        <option value="General fitness">General fitness</option>
        <option value="Run a race">Run a race</option>
        <option value="Lose weight">Lose weight</option>
        <option value="Run faster">Run faster</option>
        <option value="Other">Other</option>
      </select>
        {errors.mainGoal && (
          <p className="text-red-500 text-sm mt-1">{errors.mainGoal.message}</p>
        )}
      </div>

      {/* Motivation */}
      <div>
        <label className="block font-semibold mb-1">Motivation</label>
        <div className="space-y-1">
          {["Health", "Stress relief", "Competition", "Fun"].map((motivation) => (
            <label key={motivation} className="flex items-center space-x-2">
              <input
                type="checkbox"
                value={motivation}
                {...register("motivation")}
                defaultChecked={selectedMotivation.includes(motivation)}
              />
              <span>{motivation}</span>
            </label>
          ))}
        </div>
        {errors.motivation && (
          <p className="text-red-500 text-sm mt-1">{errors.motivation.message}</p>
        )}
      </div>
    </div>
  );
}
