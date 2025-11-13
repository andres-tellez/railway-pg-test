import React from 'react';

interface StravaAttributionProps {
  variant?: 'powered' | 'compatible';
  className?: string;
}

const StravaAttribution: React.FC<StravaAttributionProps> = ({
  variant = 'powered',
  className = "text-xs text-gray-500 mt-2"
}) => {
  const text = variant === 'powered' ? 'Powered by Strava' : 'Compatible with Strava';

  return (
    <div className={className}>
      {text}
    </div>
  );
};

export default StravaAttribution;

