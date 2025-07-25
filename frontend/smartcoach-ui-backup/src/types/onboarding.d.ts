import { OnboardingFormData } from '../schemas/OnboardingSchema';

export type StepProps = {
  formData: OnboardingFormData;
  updateFields: (fields: Partial<OnboardingFormData>) => void;
};
