import React, { useMemo, useState, useCallback } from 'react';
import ChartHelpTooltip from './ChartHelpTooltip';
import { useStaticBarStyle, getNumberDisplayClasses, getChartContainerStyle } from '../../hooks/useChartStyles';
import { calculateChartContainerHeight, calculateBarHeight } from '../../utils/chartHelpers';
import { CHART_LAYOUT, CHART_SHADOWS, CHART_BASE_CLASSES } from '../../utils/chartUtils';
import { useScrollHideTooltip } from '../../hooks/useScrollHideTooltip';

interface WeeklyPaceData {
  week: string;
  distance: number;
  runs: number;
  avgPace: string;
}

interface WeeklyPaceChartProps {
  data: WeeklyPaceData[];
  title?: string;
  totalMiles?: number;
  avgWeeklyMiles?: number;
  showHeader?: boolean;
  helpTooltip?: any;
}

export default function WeeklyPaceChart({
  data,
  title = "Pace",
  totalMiles,
  avgWeeklyMiles,
  showHeader = true,
  helpTooltip
}: WeeklyPaceChartProps) {
  const [hoveredBar, setHoveredBar] = useState<{ index: number; x: number; y: number } | null>(null);

  // Centralized tooltip behavior - hide on scroll
  useScrollHideTooltip(hoveredBar !== null, () => setHoveredBar(null));

  // Use shared memoized static style hook
  const staticBarStyle = useStaticBarStyle();

  // Memoized utility functions for better performance
  const parsePaceToMinutes = useCallback((paceString: string): number => {
    if (!paceString || paceString === '0:00') return 0;
    const parts = paceString.split(':');
    if (parts.length === 2) {
      const minutes = parseInt(parts[0], 10);
      const seconds = parseInt(parts[1], 10);
      return minutes + (seconds / 60);
    }
    return 0;
  }, []);

  const minutesToPaceString = useCallback((minutes: number): string => {
    if (minutes <= 0) return '0:00';
    const wholeMinutes = Math.floor(minutes);
    const seconds = Math.round((minutes - wholeMinutes) * 60);
    return `${wholeMinutes}:${seconds.toString().padStart(2, '0')}`;
  }, []);

  // Helper function to format dates as M/D
  const formatDate = useCallback((dateStr: string): string => {
    try {
      let date: Date;
      if (dateStr.includes('T')) {
        date = new Date(dateStr);
      } else {
        date = new Date(dateStr + 'T00:00:00');
      }

      if (isNaN(date.getTime())) {
        return dateStr;
      }

      const month = date.getMonth() + 1;
      const day = date.getDate();
      return `${month}/${day}`;
    } catch (error) {
      return dateStr;
    }
  }, []);

  // Memoize calculations for better performance
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    // Filter out invalid pace data
    const validPaceData = data.filter(d => d.avgPace && d.avgPace !== '0:00' && d.avgPace !== '');
    if (validPaceData.length === 0) return null;

    const paceValues = validPaceData.map(d => parsePaceToMinutes(d.avgPace));
    const maxPace = Math.max(...paceValues);
    const minPace = Math.min(...paceValues);
    const avgPace = paceValues.reduce((sum, pace) => sum + pace, 0) / paceValues.length;

    // Calculate pace range for normalization
    const paceRange = maxPace - minPace;

    return {
      maxPace,
      minPace,
      avgPace,
      paceRange,
      validPaceData,
      paceValues
    };
  }, [data, parsePaceToMinutes]);

  if (!chartData) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
        {showHeader && <h3 className="text-xl font-bold text-gray-900 mb-4">{title}</h3>}
        <div className="text-center py-12 text-gray-400">
          <div className="text-5xl mb-4 opacity-50">🏃</div>
          <p className="text-lg font-medium">No pace data available</p>
          <p className="text-sm mt-2">Complete runs to see pace trends</p>
        </div>
      </div>
    );
  }

  const { maxPace, minPace, avgPace, paceRange, validPaceData } = chartData;

  const helpContent = {
    title: "Pace Trends",
    quickTip: "Getting faster at the same effort level shows your fitness is improving!",
    detailedExplanation: {
      why: "Pace progression indicates fitness gains. As you get stronger, you can run faster with the same effort.",
      benefits: [
        "Shows fitness improvements objectively",
        "Helps set realistic race goals",
        "Guides workout pace selection"
      ],
      tips: [
        "Focus on easy run pace improvements first",
        "Track trends over 4-6 weeks",
        "Don't chase pace every run - effort matters more"
      ]
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100 relative">
      {showHeader && (
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-bold text-gray-900">{title}</h3>
            {helpTooltip && <ChartHelpTooltip helpContent={helpTooltip} />}
          </div>
          <div className="text-right">
            <div className="text-lg text-gray-700">
              Units: min/mi
            </div>
          </div>
        </div>
      )}

      <div className="relative">
        {(() => {
          // Calculate the total height needed for the chart container
          const totalHeight = calculateChartContainerHeight(data, (week) => {
            const paceInMinutes = parsePaceToMinutes(week.avgPace);
            // For pace, we want faster paces (lower numbers) to be higher bars
            // So we invert the calculation: (maxPace - currentPace) / paceRange
            const normalizedPace = chartData.paceRange > 0 ? (maxPace - paceInMinutes) / chartData.paceRange : 0.5;
            return calculateBarHeight(normalizedPace, 1.0); // Use 1.0 as max since normalizedPace is already 0-1
          }, CHART_LAYOUT.NUMBER_PADDING_TOP);

          return (
            <div style={getChartContainerStyle(totalHeight)}>
              {data.map((week, index) => {
                const paceInMinutes = parsePaceToMinutes(week.avgPace);

            // Skip rendering if no valid pace data
            if (paceInMinutes <= 0) {
              return (
                <div key={index} className={CHART_BASE_CLASSES.BAR_CONTAINER}>
                  <div
                    style={{
                      height: '40px',
                      width: '100%',
                      borderRadius: '0.5rem 0.5rem 0 0',
                      backgroundColor: 'rgb(229 231 235)'
                    }}
                  />

                  {/* Date below bar */}
                  <div className="text-xs text-gray-500 mt-1">
                    {formatDate(week.week)}
                  </div>
                </div>
              );
            }

            // For pace, we want faster paces (lower numbers) to be higher bars
            // So we invert the calculation: (maxPace - currentPace) / paceRange
            const normalizedPace = paceRange > 0 ? (maxPace - paceInMinutes) / paceRange : 0.5;
            const heightPixels = calculateBarHeight(normalizedPace, 1.0);
            const isCurrentWeek = index === 0;

            return (
              <div key={index} className={CHART_BASE_CLASSES.BAR_CONTAINER}>
                {/* Pace value above bar */}
                <div className={getNumberDisplayClasses('medium')}>
                  {minutesToPaceString(paceInMinutes)}
                </div>

                <div
                  className={`${CHART_BASE_CLASSES.BAR} bg-blue-500`}
                  style={{
                    ...staticBarStyle,
                    height: `${heightPixels}px`,
                    boxShadow: CHART_SHADOWS.BLUE
                  }}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setHoveredBar({
                      index,
                      x: rect.left + rect.width / 2,
                      y: rect.top - 10
                    });
                  }}
                  onMouseLeave={() => setHoveredBar(null)}
                />

                {/* Date below bar */}
                <div className="text-xs text-gray-500 mt-1">
                  {formatDate(week.week)}
                </div>
              </div>
            );
          })}
            </div>
          );
        })()}

        {/* Custom Tooltip */}
        {hoveredBar && (
          <div
            className="fixed z-50 px-2 py-1 bg-gray-800 text-white text-xs rounded shadow-lg pointer-events-none transition-all duration-100 ease-out transform"
            style={{
              left: `${hoveredBar.x}px`,
              top: `${hoveredBar.y}px`,
              transform: 'translateX(-50%) translateY(-100%)',
              opacity: hoveredBar ? 1 : 0,
              animation: 'fadeInUp 0.1s ease-out'
            }}
          >
            <div className={CHART_BASE_CLASSES.TOOLTIP_CONTAINER}>
              <div>
                {(() => {
                  try {
                    const dateStr = data[hoveredBar.index].week;
                    // Handle different date formats
                    if (dateStr.includes('T')) {
                      // Already has time component
                      return new Date(dateStr).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                      });
                    } else {
                      // Add time component to make it local time
                      return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                      });
                    }
                  } catch (error) {
                    // Fallback if date parsing fails
                    return data[hoveredBar.index].week;
                  }
                })()}
              </div>
              <div className="text-blue-300">
                {data[hoveredBar.index].avgPace} min/mi
              </div>
            </div>
            {/* Arrow pointing down */}
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-3 border-r-3 border-t-3 border-transparent border-t-gray-800"></div>
          </div>
        )}
      </div>
    </div>
  );
}
