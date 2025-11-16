import React, { useState, useMemo } from "react";
import { useStaticBarStyle, getBarColorClasses, getNumberDisplayClasses, getChartContainerStyle } from '../../hooks/useChartStyles';
import { getBarShadow, formatChartNumber, calculateChartContainerHeight, calculateBarHeight } from '../../utils/chartHelpers';
import { CHART_LAYOUT, CHART_BASE_CLASSES } from '../../utils/chartUtils';
import { useScrollHideTooltip } from '../../hooks/useScrollHideTooltip';
import ChartTooltip from './ChartTooltip';

interface LongestRunData {
  week_start: string;
  activity_id: number;
  name: string;
  date: string;
  distance: number;
  pace: string;
  duration: string;
  heart_rate_zones: any;
  is_personal_record: boolean;
  is_significant_drop: boolean;
  trend: 'improving' | 'declining' | 'stable';
  change_pct: number;
  prev_week_distance: number | null;
}

type WeeklyLongRunGoal = { week: string; long_run_miles: number };

interface LongestRunsChartProps {
  data: LongestRunData[];
  title?: string;
  showHeader?: boolean;
  longRunGoals?: WeeklyLongRunGoal[];
}

export default function LongestRunsChart({ data, title = "Weekly Longest Runs", showHeader = true, longRunGoals = [] }: LongestRunsChartProps) {
  const [hoveredRun, setHoveredRun] = useState<{ index: number; x: number; y: number } | null>(null);

  // Centralized tooltip behavior - hide on scroll
  useScrollHideTooltip(hoveredRun !== null, () => setHoveredRun(null));

  // Optimized chart data calculation (simplified - focus on longest runs only)
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    // Helper to find a planned value for the week (match both YYYY-MM-DD and with 'T')
    const findPlannedForWeek = (week: string): number | null => {
      const goal = longRunGoals.find(g => {
        const gw = g.week;
        if (gw === week) return true;
        if (week.includes('T') && gw === week.split('T')[0]) return true;
        if (gw.includes('T') && week === gw.split('T')[0]) return true;
        return false;
      });
      return goal ? goal.long_run_miles : null;
    };

    // Calculate chart maximum considering both actual longest run and planned miles
    const allActual = data.map(run => run.distance);
    const allPlanned = data.map(run => findPlannedForWeek(run.week_start) || 0);
    const maxDistance = Math.max(...allActual, ...allPlanned, 1);

    // Calculate bar colors based on data
    // Per request: remove special colors (no green PR or red drop) → always normal (blue)
    const barColors = data.map(() => 'normal');

    // Pre-calculate all bar data to avoid calculations in render loop
    const barData = data.map((run, index) => {
      const heightPixels = calculateBarHeight(run.distance, maxDistance);
      const planned = findPlannedForWeek(run.week_start);
      const plannedHeightPixels = planned ? calculateBarHeight(planned, maxDistance) : 0;
      const isCurrentWeek = index === 0;
      const barColor = barColors[index];

      return {
        heightPixels,
        isCurrentWeek,
        barColor,
        planned,
        plannedHeightPixels
      };
    });

    return { maxDistance, barColors, barData };
  }, [data, longRunGoals]);

  if (!chartData) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
        {showHeader && <h3 className="text-xl font-bold text-gray-900">{title}</h3>}
        <div className="text-center text-gray-400 py-12">
          No runs found for the selected time period
        </div>
      </div>
    );
  }

  const { maxDistance, barColors, barData } = chartData;

  // Use shared memoized static style hook
  const staticBarStyle = useStaticBarStyle();

  // Calculate height in pixels (centralized approach)
  const calculateHeight = (distance: number) => {
    return calculateBarHeight(distance, maxDistance);
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      const month = date.getMonth() + 1; // getMonth() is 0-indexed
      const day = date.getDate();
      return `${month}/${day}`;
    } catch (error) {
      return dateString; // fallback to original string if parsing fails
    }
  };

  // Use shared bar color classes function
  const getRunColorClasses = getBarColorClasses;

  // Use shared getBarShadow function
  const getBarShadowForLongestRuns = (barColor: string, index: number): string => {
    return getBarShadow(barColor, index);
  };


  return (
    <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
      {showHeader && (
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-bold text-gray-900">{title}</h3>
          <div className="text-right">
            <div className="text-lg text-gray-700">
              Units: mi
            </div>
          </div>
        </div>
      )}

      {data.length === 0 ? (
        <div className="text-center text-gray-400 py-12">
          No runs found for the selected time period
        </div>
      ) : (
        <div>
          {/* Bar Chart */}
          {(() => {
            // Calculate the total height needed for the chart container
            const totalHeight = calculateChartContainerHeight(data, (run) => calculateHeight(run.distance), CHART_LAYOUT.NUMBER_PADDING_TOP);

            return (
              <div style={getChartContainerStyle(totalHeight)}>
                {data.map((run, index) => {
                  const barInfo = barData[index];
                  const { heightPixels, isCurrentWeek, barColor } = barInfo;
                  const colorClasses = getRunColorClasses(barColor, isCurrentWeek);

              return (
              <div
                key={run.activity_id}
                className={CHART_BASE_CLASSES.BAR_CONTAINER}
              >
                {/* Bars container (Actual + Planned side-by-side, equal widths) */}
                <div className="relative w-full" style={{ height: `${Math.max(heightPixels, barData[index].plannedHeightPixels)}px` }}>
                  {/* Actual (left) */}
                  <div
                    className={colorClasses}
                    onMouseEnter={(e) => {
                      const rect = e.currentTarget.getBoundingClientRect();
                      setHoveredRun({
                        index,
                        x: rect.left + rect.width / 2,
                        y: rect.top - 10,
                      });
                    }}
                    onMouseLeave={() => setHoveredRun(null)}
                    style={{
                      ...staticBarStyle,
                      position: 'absolute',
                      left: 0,
                      bottom: 0,
                      width: barData[index].planned ? '48%' : '100%',
                      height: `${heightPixels}px`
                    }}
                  >
                    {/* Label inside actual bar */}
                    <div className="absolute top-1 left-1/2 -translate-x-1/2 text-[10px] sm:text-xs font-semibold text-white drop-shadow" aria-hidden="true">
                      {formatChartNumber(run.distance, 'distance')}
                    </div>
                  </div>

                  {/* Planned (right) */}
                  {barData[index].planned && (
                    <div
                      className="absolute right-0 bg-gray-400/70 ring-1 ring-gray-300"
                      style={{
                        borderRadius: '0.5rem 0.5rem 0 0',
                        bottom: 0,
                        width: '48%',
                        height: `${barData[index].plannedHeightPixels}px`
                      }}
                      aria-label={`Planned ${barData[index].planned?.toFixed(1)} miles`}
                      role="img"
                    >
                      <div className="absolute top-1 left-1/2 -translate-x-1/2 text-[10px] sm:text-xs font-semibold text-gray-900" aria-hidden="true">
                        {barData[index].planned?.toFixed(1)}
                      </div>
                    </div>
                  )}
                </div>

                {/* Labels */}
                <div className="mt-2 text-center">
                  <div className="text-xs text-gray-500">
                    {formatDate(run.week_start)}
                  </div>
                </div>
              </div>
              );
            })}
              </div>
            );
          })()}

          {/* Centralized Tooltip */}
          <ChartTooltip
            isVisible={hoveredRun !== null}
            position={hoveredRun ? { x: hoveredRun.x, y: hoveredRun.y } : { x: 0, y: 0 }}
            data={{
              week: hoveredRun ? data[hoveredRun.index].week_start : '',
              runName: hoveredRun ? data[hoveredRun.index].name : undefined,
              runDistance: hoveredRun ? data[hoveredRun.index].distance : undefined,
              runPace: hoveredRun ? data[hoveredRun.index].pace : undefined,
              runDuration: hoveredRun ? data[hoveredRun.index].duration : undefined,
              runHRZones: hoveredRun ? data[hoveredRun.index].heart_rate_zones : undefined,
              isPersonalRecord: hoveredRun ? data[hoveredRun.index].is_personal_record : undefined,
              isSignificantDrop: hoveredRun ? data[hoveredRun.index].is_significant_drop : undefined,
              prevWeekDistance: hoveredRun ? data[hoveredRun.index].prev_week_distance : undefined,
              prevWeekPace: hoveredRun && hoveredRun.index < data.length - 1 ? data[hoveredRun.index + 1].pace : undefined
            }}
          />

          {/* Legend positioned below bars on the right (no Significant Drop) */}
          <div className="flex justify-end mt-4">
            <div className="flex gap-6 text-sm text-gray-600">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-500 rounded"></div>
                <span>Actual</span>
              </div>
              {longRunGoals && longRunGoals.length > 0 && (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-gray-400 rounded ring-1 ring-gray-300"></div>
                  <span>Planned</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
