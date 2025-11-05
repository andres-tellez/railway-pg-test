import React, { useMemo, memo } from "react";

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  color: "blue" | "purple";
}

const FeatureCard: React.FC<FeatureCardProps> = ({ icon, title, description, color }) => {
  // Memoize color classes to avoid recalculation on every render
  const classes = useMemo(() => {
    const isBlue = color === "blue";
    return {
      bgColor: isBlue ? "bg-blue-50" : "bg-purple-50",
      borderColor: isBlue ? "border-blue-100" : "border-purple-100",
      iconBg: isBlue ? "bg-blue-100" : "bg-purple-100",
      iconText: isBlue ? "text-blue-600" : "text-purple-600",
    };
  }, [color]);

  return (
    <div className={`flex items-start gap-3 ${classes.bgColor} rounded-lg p-4 border ${classes.borderColor}`}>
      <div className={`w-10 h-10 ${classes.iconBg} rounded-xl flex items-center justify-center flex-shrink-0`}>
        <div className={classes.iconText}>{icon}</div>
      </div>
      <div>
        <h3 className="text-base font-bold text-gray-900 mb-1">{title}</h3>
        <p className="text-sm text-gray-700 leading-relaxed">{description}</p>
      </div>
    </div>
  );
};

// Memoize component to prevent unnecessary re-renders
export const FeatureCardMemoized = memo(FeatureCard);
export { FeatureCardMemoized as FeatureCard };
