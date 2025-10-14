import React, { useState, useRef } from 'react';
import { useScrollHideTooltip } from '../../hooks/useScrollHideTooltip';

interface HelpContent {
  title: string;
  quickTip: string;
  detailedExplanation: {
    why: string;
    benefits: string[];
    tips: string[];
  };
}

interface ChartHelpTooltipProps {
  helpContent: HelpContent;
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
}

interface TooltipPosition {
  vertical: 'above' | 'below';
  horizontal: 'left' | 'right' | 'center';
  x: number;
  y: number;
}

export default function ChartHelpTooltip({
  helpContent,
  position = 'top-right'
}: ChartHelpTooltipProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition>({
    vertical: 'below',
    horizontal: 'right',
    x: 0,
    y: 0
  });
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Centralized tooltip behavior - hide on scroll
  useScrollHideTooltip(isExpanded, () => setIsExpanded(false));


  return (
    <div className="relative z-10">
      {/* Help Button */}
      <button
        ref={buttonRef}
        className="w-6 h-6 rounded-full bg-gray-300 hover:bg-gray-400 flex items-center justify-center transition-all duration-200 group ml-2 border-2 border-gray-400 hover:border-gray-500 shadow-md hover:shadow-lg"
        onMouseEnter={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          setTooltipPosition({
            vertical: 'below',
            horizontal: 'right',
            x: rect.right + 10,
            y: rect.top + rect.height / 2
          });
          setIsExpanded(true);
        }}
        onMouseLeave={() => setIsExpanded(false)}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="text-gray-700 text-sm font-bold group-hover:text-gray-900">?</span>
      </button>

      {/* Tooltip - same as bar chart */}
      {isExpanded && (
        <div
          className="fixed z-50 w-80 bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-600 rounded-lg p-3 shadow-2xl pointer-events-none backdrop-blur-sm"
          style={{
            left: `${tooltipPosition.x}px`,
            top: `${tooltipPosition.y}px`,
            transform: 'translateY(-50%)',
            backdropFilter: 'blur(8px)',
          }}
        >

          <div className="flex items-start justify-between mb-2">
            <h4 className="text-white font-bold text-sm bg-gray-700/30 rounded px-2 py-1">{helpContent.title}</h4>
          </div>

          {/* Quick Tip */}
          <div className="mb-3">
            <p className="text-sm text-gray-300 leading-relaxed">{helpContent.quickTip}</p>
          </div>

          {/* Detailed Explanation */}
          <div className="space-y-2">
            <div>
              <h5 className="text-xs font-semibold text-gray-300 mb-1">Why it matters:</h5>
              <p className="text-xs text-gray-400 leading-relaxed">{helpContent.detailedExplanation.why}</p>
            </div>

            <div>
              <h5 className="text-xs font-semibold text-gray-300 mb-1">Key benefits:</h5>
              <ul className="text-xs text-gray-400 space-y-1">
                {helpContent.detailedExplanation.benefits.map((benefit, index) => (
                  <li key={index} className="flex items-start">
                    <span className="text-blue-400 mr-2 mt-0.5">•</span>
                    <span>{benefit}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h5 className="text-xs font-semibold text-gray-300 mb-1">Training tips:</h5>
              <ul className="text-xs text-gray-400 space-y-1">
                {helpContent.detailedExplanation.tips.map((tip, index) => (
                  <li key={index} className="flex items-start">
                    <span className="text-green-400 mr-2 mt-0.5">→</span>
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
