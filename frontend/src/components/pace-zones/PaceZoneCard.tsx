import React from 'react';
import type { PaceZoneInfo } from '@/types/paceZones';

interface PaceZoneCardProps {
  info: PaceZoneInfo;
  paceRange: string;
  isExpanded: boolean;
  onToggle: () => void;
}

const PaceZoneCard: React.FC<PaceZoneCardProps> = ({
  info,
  paceRange,
  isExpanded,
  onToggle,
}) => {
  // Map color names to Tailwind classes
  const colorClasses: Record<string, { border: string; bg: string; text: string }> = {
    red: { border: 'border-red-400', bg: 'bg-red-100', text: 'text-red-800' },
    orange: { border: 'border-orange-400', bg: 'bg-orange-100', text: 'text-orange-800' },
    yellow: { border: 'border-yellow-400', bg: 'bg-yellow-100', text: 'text-yellow-800' },
    green: { border: 'border-green-400', bg: 'bg-green-100', text: 'text-green-800' },
  };

  const colorClass = colorClasses[info.color] || colorClasses.green;

  return (
    <div
      className={`bg-white rounded-xl shadow-md border-2 transition-all duration-200 ${
        isExpanded
          ? `${colorClass.border} shadow-lg`
          : 'border-gray-200 hover:border-gray-300'
      }`}
    >
      {/* Card Header - Always Visible */}
      <button
        onClick={onToggle}
        className="w-full text-left p-6 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded-t-xl"
        aria-expanded={isExpanded}
        aria-label={`${info.name} pace zone details`}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-4 flex-1">
            <div className="text-4xl">{info.icon}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2 mb-2">
                <h3 className="text-xl md:text-2xl font-bold text-gray-900">
                  {info.name}
                </h3>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${colorClass.bg} ${colorClass.text}`}
                >
                  <span className="mr-1">{info.tagIcon}</span>
                  {info.tag}
                </span>
              </div>
              <p className="text-lg font-semibold text-gray-700 mb-1">
                {paceRange}
              </p>
              <p className="text-sm text-gray-600">RPE: {info.rpe}</p>
            </div>
          </div>
          <div className="ml-4 flex-shrink-0">
            <svg
              className={`w-6 h-6 text-gray-400 transition-transform duration-200 ${
                isExpanded ? 'transform rotate-180' : ''
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        </div>
      </button>

      {/* Expandable Content */}
      <div
        className={`overflow-hidden transition-all duration-200 ease-in-out ${
          isExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="px-6 pb-6 space-y-4 border-t border-gray-200 pt-4">
          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-2">
              What is this pace?
            </h4>
            <p className="text-gray-700 leading-relaxed">{info.description}</p>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-2">
              When to use
            </h4>
            <p className="text-gray-700 leading-relaxed">{info.whenToUse}</p>
          </div>

          <div className="flex items-center space-x-4 text-sm text-gray-600">
            <div>
              <span className="font-semibold">Typical Duration:</span>{' '}
              {info.typicalDuration}
            </div>
            <div>
              <span className="font-semibold">% of Training:</span>{' '}
              {info.percentage}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PaceZoneCard;
