// src/components/ui/TextInput.tsx
import React from "react";

type Props = React.InputHTMLAttributes<HTMLInputElement>;

const TextInput = React.forwardRef<HTMLInputElement, Props>(({ className = "", ...props }, ref) => (
  <input
    ref={ref}
    {...props}
    className={`w-full p-2 border rounded shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${className}`}
  />
));

export default TextInput;
