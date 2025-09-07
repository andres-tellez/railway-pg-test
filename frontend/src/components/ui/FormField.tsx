// src/components/ui/FormField.tsx
import React from "react";
import { FieldError } from "react-hook-form";

interface Props {
  label: string;
  error?: FieldError;
  children: React.ReactNode;
}

const FormField: React.FC<Props> = ({ label, error, children }) => {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
      {error && <p className="text-sm text-red-600 mt-1">{error.message}</p>}
    </div>
  );
};

export default FormField;
