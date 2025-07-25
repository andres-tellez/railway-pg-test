import { OnboardingFormData } from '../../../schemas/onboardingSchema';

type Props = {
  formData: Partial<OnboardingFormData>;
  updateFields: (fields: Partial<OnboardingFormData>) => void;
};

export default function RunnerLevelStep({ formData, updateFields }: Props) {
  return (
    <div>
      <h2>Runner Level</h2>
      <p>Current level: {formData.runnerLevel ?? 'Not selected'}</p>
      <button onClick={() => updateFields({ runnerLevel: 'Beginner' })}>Beginner</button>
    </div>
  );
}
