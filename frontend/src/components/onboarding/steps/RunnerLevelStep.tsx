import { useFormContext } from "react-hook-form";
import FormField from "@/components/ui/FormField";
import RadioGroup from "@/components/ui/RadioGroup";

const RunnerLevelStep = () => {
  const { register, formState: { errors } } = useFormContext();

  return (
    <FormField label="Runner Level" error={errors.runnerLevel}>
      <RadioGroup
        name="runnerLevel"
        register={register}
        options={[
          { value: "Beginner", label: "Beginner" },
          { value: "Intermediate", label: "Intermediate" },
          { value: "Expert", label: "Expert" }, // <-- previously "Advanced"
        ]}
      />
    </FormField>
  );
};

export default RunnerLevelStep;
