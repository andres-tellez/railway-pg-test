// src/components/ui/SelectInput.tsx
import React from "react";

type Props = React.SelectHTMLAttributes<HTMLSelectElement>;

const SelectInput = React.forwardRef<HTMLSelectElement, Props>((props, ref) => (
  <select
    ref={ref}
    {...props}
    className={`w-full p-2 border rounded shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${props.className ?? ""}`}
  />
));

export default SelectInput;
