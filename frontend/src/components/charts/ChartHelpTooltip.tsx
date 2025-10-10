import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';

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
  const tooltipRef = useRef<HTMLDivElement>(null);
  const positionCalculatedRef = useRef(false);
  const lastButtonPositionRef = useRef({ x: 0, y: 0 });
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Simple positioning calculation
  const calculatePosition = useCallback(() => {
    if (!buttonRef.current) return;

    const buttonRect = buttonRef.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Tooltip dimensions
    const tooltipWidth = 320;
    const tooltipHeight = 200;

    // Calculate available space
    const spaceBelow = viewportHeight - buttonRect.bottom;
    const spaceAbove = buttonRect.top;
    const spaceRight = viewportWidth - buttonRect.right;
    const spaceLeft = buttonRect.left;

    // Determine vertical position
    let vertical: 'above' | 'below' = 'below';
    if (spaceBelow < tooltipHeight && spaceAbove > tooltipHeight) {
      vertical = 'above';
    }

    // Determine horizontal position
    let horizontal: 'left' | 'right' | 'center' = 'right';

    if (spaceRight < tooltipWidth && spaceLeft > tooltipWidth) {
      horizontal = 'left';
    } else if (spaceRight < tooltipWidth / 2 && spaceLeft < tooltipWidth / 2) {
      horizontal = 'center';
    }

    // Calculate exact positioning
    let x = 0;
    let y = 0;

    if (horizontal === 'left') {
      x = buttonRect.left - tooltipWidth - 8;
    } else if (horizontal === 'right') {
      x = buttonRect.right + 8;
    } else { // center
      x = buttonRect.left + (buttonRect.width / 2) - (tooltipWidth / 2);
    }

    if (vertical === 'above') {
      y = buttonRect.top - tooltipHeight - 8;
    } else {
      y = buttonRect.bottom + 8;
    }

    // Clamp to viewport bounds
    x = Math.max(8, Math.min(x, viewportWidth - tooltipWidth - 8));
    y = Math.max(8, Math.min(y, viewportHeight - tooltipHeight - 8));

    setTooltipPosition({ vertical, horizontal, x, y });
  }, []);

  // Calculate position when tooltip opens
  useEffect(() => {
    if (isExpanded) {
      calculatePosition();
    }
  }, [isExpanded, calculatePosition]);

  // Handle scroll and resize
  useEffect(() => {
    if (isExpanded) {
      const handleScroll = () => calculatePosition();
      const handleResize = () => calculatePosition();

      window.addEventListener('scroll', handleScroll, { passive: true });
      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('scroll', handleScroll);
        window.removeEventListener('resize', handleResize);
      };
    }
  }, [isExpanded, calculatePosition]);

  // Hover handlers with delay to prevent flickering
  const handleMouseEnter = useCallback(() => {
    // Clear any pending hide timeout
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }

    // Only show if not already showing
    if (!isExpanded) {
      // Clear any existing hover timeout
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }

      // Add delay before showing to prevent flickering
      hoverTimeoutRef.current = setTimeout(() => {
        setIsExpanded(true);
      }, 200); // 200ms delay
    }
  }, [isExpanded]);

  const handleMouseLeave = useCallback(() => {
    // Clear any pending show timeout
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
      hoverTimeoutRef.current = null;
    }

    // Add delay before hiding to prevent flickering
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
    }

    hideTimeoutRef.current = setTimeout(() => {
      setIsExpanded(false);
    }, 100); // 100ms delay
  }, []);

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
      if (hideTimeoutRef.current) {
        clearTimeout(hideTimeoutRef.current);
      }
    };
  }, []);

  return (
    <div className="relative z-10">
      {/* Help Button */}
      <button
        ref={buttonRef}
        className="w-5 h-5 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors duration-200 group ml-2"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="text-gray-500 text-xs font-medium group-hover:text-gray-700">?</span>
      </button>

      {/* Tooltip with smart positioning */}
      {isExpanded && (
        <>
          {/* Backdrop to close tooltip when clicking outside */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsExpanded(false)}
            onMouseEnter={handleMouseLeave}
          />

          {/* Tooltip */}
          <div
            ref={tooltipRef}
            className="fixed z-50 w-80 bg-gray-800 text-white rounded-lg shadow-xl border border-gray-700 p-4 transition-all duration-200 ease-out"
            style={{
              left: `${tooltipPosition.x}px`,
              top: `${tooltipPosition.y}px`,
              transform: 'translateZ(0)', // Force hardware acceleration
              pointerEvents: 'none', // Prevent tooltip from intercepting mouse events
            }}
          >
            {/* Arrow pointer */}
            <div
              className={`absolute w-0 h-0 ${
                tooltipPosition.vertical === 'above'
                  ? 'border-t-gray-800 border-t-4'
                  : 'border-b-gray-800 border-b-4'
              } ${
                tooltipPosition.horizontal === 'left'
                  ? 'border-l-4 border-r-4 border-l-transparent border-r-transparent left-4'
                  : tooltipPosition.horizontal === 'right'
                  ? 'border-l-4 border-r-4 border-l-transparent border-r-transparent right-4'
                  : 'border-l-4 border-r-4 border-l-transparent border-r-transparent left-1/2 transform -translate-x-1/2'
              } ${
                tooltipPosition.vertical === 'above' ? 'top-full' : 'bottom-full'
              }`}
            />

            <div className="flex items-start justify-between mb-3" style={{ pointerEvents: 'auto' }}>
              <h4 className="text-sm font-semibold text-white">{helpContent.title}</h4>
              <button
                className="text-gray-400 hover:text-gray-200 text-xs transition-colors"
                onClick={() => setIsExpanded(false)}
                style={{ pointerEvents: 'auto' }}
              >
                ✕
              </button>
            </div>

            {/* Quick Tip */}
            <div className="mb-4">
              <p className="text-sm text-gray-200 leading-relaxed">{helpContent.quickTip}</p>
            </div>

            {/* Detailed Explanation */}
            <div className="space-y-3">
              <div>
                <h5 className="text-xs font-semibold text-gray-100 mb-1">Why it matters:</h5>
                <p className="text-xs text-gray-300 leading-relaxed">{helpContent.detailedExplanation.why}</p>
              </div>

              <div>
                <h5 className="text-xs font-semibold text-gray-100 mb-1">Key benefits:</h5>
                <ul className="text-xs text-gray-300 space-y-1">
                  {helpContent.detailedExplanation.benefits.map((benefit, index) => (
                    <li key={index} className="flex items-start">
                      <span className="text-blue-400 mr-2 mt-0.5">•</span>
                      <span>{benefit}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h5 className="text-xs font-semibold text-gray-100 mb-1">Training tips:</h5>
                <ul className="text-xs text-gray-300 space-y-1">
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
        </>
      )}
    </div>
  );
}
