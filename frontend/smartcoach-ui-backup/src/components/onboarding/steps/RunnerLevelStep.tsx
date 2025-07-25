import React from 'react';

interface Props {
  formData: any;
  updateFields: (fields: Partial<any>) => void;
}

export default function RunnerLevelStep({ formData, updateFields }: Props) {
  return (
    <div>
      <h2 className="text-xl font-semibold">Runner Level</h2>
      {/* Replace this with actual form fields */}
      <p>Current level: {formData.runnerLevel || 'Not selected'}</p>
    </div>
  );
}
