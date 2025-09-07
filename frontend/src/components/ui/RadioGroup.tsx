// src/components/ui/RadioGroup.tsx
import React from "react";

interface Option {
  label: string;
  value: string;
}

interface Props {
  name: string;
  options: Option[];
  register: any;
}

const RadioGroup: React.FC<Props> = ({ name, options, register }) => {
  return (
    <div className="space-y-2">
      {options.map((opt) => (
        <label key={opt.value} className="flex items-center space-x-2">
          <input
            type="radio"
            value={opt.value}
            {...register(name)}
            className="text-blue-600"
          />
          <span>{opt.label}</span>
        </label>
      ))}
    </div>
  );
};

export default RadioGroup;
