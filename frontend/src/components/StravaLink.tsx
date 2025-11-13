import React from 'react';

interface StravaLinkProps {
  activityId: string | number;
  className?: string;
  children?: React.ReactNode;
}

const StravaLink: React.FC<StravaLinkProps> = ({
  activityId,
  className = "text-[#FC5200] hover:underline font-medium",
  children
}) => {
  const stravaUrl = `https://www.strava.com/activities/${activityId}`;

  return (
    <a
      href={stravaUrl}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
    >
      {children || "View on Strava"}
    </a>
  );
};

export default StravaLink;

