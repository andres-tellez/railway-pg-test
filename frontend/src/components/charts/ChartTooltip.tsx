import React from 'react';
import { formatWeekString, formatChangePercentage, getTrendIcon } from '../../utils/chartHelpers';
import { useUnitSystem } from '../../context/UnitSystemContext';
import { formatDistance, formatPace } from '../../utils/unitFormatters';

// Helper function to format heart rate zones
const formatHeartRateZones = (zones: any) => {
  if (!zones) return null;
  return (
    <div className="space-y-1">
      {Object.entries(zones).map(([zone, percentage]) => (
        <div key={zone} className="flex justify-between text-xs">
          <span className="text-gray-400">{zone}:</span>
          <span className="text-white font-semibold">{Number(percentage).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
};

// Helper function to format pace comparison with color info
const formatPaceComparison = (currentPace: string, prevPace?: string): { text: string; isFaster: boolean | null } => {
  if (!prevPace) return { text: currentPace, isFaster: null };

  // Parse current and previous pace (assuming format like "9:33")
  const parsePace = (paceStr: string) => {
    const [minutes, seconds] = paceStr.split(':').map(Number);
    return minutes + seconds / 60;
  };

  const currentPaceNum = parsePace(currentPace);
  const prevPaceNum = parsePace(prevPace);
  const paceDiff = currentPaceNum - prevPaceNum;

  if (Math.abs(paceDiff) < 0.1) return { text: currentPace, isFaster: null }; // No significant difference

  // Convert to seconds difference for cleaner display
  const secondsDiff = Math.round(paceDiff * 60);
  const sign = secondsDiff > 0 ? '+' : '-';
  const diffStr = `${sign}${Math.abs(secondsDiff)} sec`;

  return {
    text: `${currentPace} min/mi  |  ${diffStr}`,
    isFaster: paceDiff < 0 // Negative diff means faster (better)
  };
};

interface ChartTooltipProps {
  isVisible: boolean;
  position: { x: number; y: number };
  data: {
    // Common fields
    week: string;
    additionalInfo?: React.ReactNode;

    // Weekly aggregated data (for Pace, VO2, etc.)
    value?: number;
    unit?: string;
    runs?: number;
    distance?: number;
    trend?: 'improving' | 'declining' | 'stable';
    changePct?: number;

    // Individual run data (for Longest Runs)
    runName?: string;
    runDistance?: number;
    runPace?: string;
    runDuration?: string;
    runHRZones?: any;
    isPersonalRecord?: boolean;
    isSignificantDrop?: boolean;
    prevWeekDistance?: number;
    prevWeekPace?: string;
  };
}

export default function ChartTooltip({ isVisible, position, data }: ChartTooltipProps) {
  const { unitSystem } = useUnitSystem();

  if (!isVisible) return null;

  // Determine if this is individual run data or weekly aggregated data
  const isRunData = data.runName !== undefined;

  return (
        <div
          className="fixed z-50 bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-600 rounded-lg p-3 shadow-2xl pointer-events-none backdrop-blur-sm"
          style={{
            left: `${position.x}px`,
            top: `${position.y}px`,
            transform: 'translate(-50%, -100%)',
            minWidth: '240px',
            backdropFilter: 'blur(8px)',
          }}
        >
      {/* Date Header */}
      <div className="text-white font-bold text-sm mb-2 text-center bg-gray-700/30 rounded px-2 py-1">
        {formatWeekString(data.week)}
      </div>

      <div className="space-y-1.5 text-sm">
        {/* Individual Run Data */}
        {isRunData && (
          <>
            {/* Run Name */}
            <div className="text-white font-semibold mb-2 text-sm">
              {data.runName}
            </div>

              {/* Run Stats - Organized in columns */}
              <div className="space-y-2 text-sm">
                {/* Distance */}
                <div className="flex items-center justify-between">
                  <span className="text-gray-300">Distance:</span>
                  <span className="text-white font-semibold">{data.runDistance ? formatDistance(data.runDistance, unitSystem, 1) : 'N/A'}</span>
                </div>

                {/* Duration */}
                <div className="flex items-center justify-between">
                  <span className="text-gray-300">Duration:</span>
                  <span className="text-white font-semibold">{data.runDuration}</span>
                </div>

                {/* Second Row: Pace with Trend */}
                <div className="flex items-center justify-between">
                  <span className="text-gray-300">Pace:</span>
                  <span className={`font-semibold ${
                    (() => {
                      const paceInfo = formatPaceComparison(data.runPace || '', data.prevWeekPace);
                      if (paceInfo.isFaster === true) return 'text-green-400';
                      if (paceInfo.isFaster === false) return 'text-red-400';
                      return 'text-white';
                    })()
                  }`}>
                    {formatPaceComparison(data.runPace || '', data.prevWeekPace).text}
                  </span>
                </div>

                {/* Distance Trend - Only show if significant */}
                {data.prevWeekDistance && Math.abs((data.runDistance || 0) - data.prevWeekDistance) > 0.5 && (
                  <div className="flex items-center justify-between">
                    <span className="text-gray-300">Trend:</span>
                    <span className={`font-semibold ${
                      data.runDistance && data.prevWeekDistance ?
                        (data.runDistance >= data.prevWeekDistance ? 'text-green-400' : 'text-red-400') :
                        'text-white'
                    }`}>
                      {data.runDistance && data.prevWeekDistance ?
                        `${data.runDistance >= data.prevWeekDistance ? '+' : ''}${formatDistance(Math.abs(data.runDistance - data.prevWeekDistance), unitSystem, 1)}` :
                        'N/A'
                      }
                    </span>
                  </div>
                )}

                {/* Special Badges */}
                {(data.isPersonalRecord || data.isSignificantDrop) && (
                  <div className="pt-1 border-t border-gray-700 text-center">
                    {data.isPersonalRecord && (
                      <span className="text-green-400 font-semibold text-xs mr-3">🏆 Personal Record!</span>
                    )}
                    {data.isSignificantDrop && (
                      <span className="text-red-400 font-semibold text-xs">⚠️ Significant Drop</span>
                    )}
                  </div>
                )}

              </div>
          </>
        )}

        {/* Weekly Aggregated Data */}
        {!isRunData && (
          <>
            {data.value !== undefined && (
              <div className="flex items-center justify-between">
                <span className="text-gray-300 font-medium">Value:</span>
                <span className="text-white font-semibold">
                  {data.unit === 'min/mi' || data.unit === 'min/km' ?
                    (() => {
                      // Convert minutes per mile to seconds per mile, then format
                      const secondsPerMile = data.value * 60;
                      return formatPace(secondsPerMile, unitSystem);
                    })() :
                    `${data.value} ${data.unit}`
                  }
                </span>
              </div>
            )}

            {data.runs && (
              <div className="flex items-center justify-between">
                <span className="text-gray-300 font-medium">Runs:</span>
                <span className="text-white font-semibold">{data.runs}</span>
              </div>
            )}

            {data.distance && (
              <div className="flex items-center justify-between">
                <span className="text-gray-300 font-medium">Distance:</span>
                <span className="text-white font-semibold">{data.distance.toFixed(1)} mi</span>
              </div>
            )}

            {data.trend && (
              <div className="flex items-center justify-between">
                <span className="text-gray-300 font-medium">Trend:</span>
                <span className="text-white font-semibold">
                  {getTrendIcon(data.trend)} {data.trend}
                </span>
              </div>
            )}

            {data.changePct !== undefined && (
              <div className="flex items-center justify-between">
                <span className="text-gray-300 font-medium">Change:</span>
                <span className={`font-semibold ${
                  data.unit === 'min/mi'
                    ? (data.changePct <= 0 ? 'text-green-400' : 'text-red-400') // For pace: negative = faster = good (green)
                    : (data.changePct >= 0 ? 'text-green-400' : 'text-red-400')  // For other metrics: positive = good (green)
                }`}>
                  {formatChangePercentage(data.changePct)}
                </span>
              </div>
            )}
          </>
        )}

        {data.additionalInfo}
      </div>
    </div>
  );
}
