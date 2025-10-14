import React, { useMemo, useState, useCallback } from 'react';
import ChartHelpTooltip from './ChartHelpTooltip';
import ChartTooltip from './ChartTooltip';
import { useStaticBarStyle, getNumberDisplayClasses, getChartContainerStyle } from '../../hooks/useChartStyles';
import { CHART_LAYOUT, CHART_SHADOWS, CHART_BASE_CLASSES } from '../../utils/chartUtils';
import { formatChartNumber, calculateChartContainerHeight } from '../../utils/chartHelpers';
import { useScrollHideTooltip } from '../../hooks/useScrollHideTooltip';

interface WeeklyVO2Data {
  week: string;
  vo2_estimate: number | null;
  run_score: number | null;
  runs?: number;
  distance?: number;
}

interface WeeklyVO2ChartProps {
  data: WeeklyVO2Data[];
  title?: string;
  showHeader?: boolean;
  helpTooltip?: any;
}

export default function WeeklyVO2Chart({
  data,
  title = "VO2 Max Estimate",
  showHeader = true,
  helpTooltip
}: WeeklyVO2ChartProps) {
  const [hoveredBar, setHoveredBar] = useState<{ index: number; x: number; y: number } | null>(null);

  // Centralized tooltip behavior - hide on scroll
  useScrollHideTooltip(hoveredBar !== null, () => setHoveredBar(null));

  // Use shared memoized static style hook
  const staticBarStyle = useStaticBarStyle();

  // Helper function to determine fitness level context
  const getFitnessLevel = useCallback((vo2: number): string => {
    if (vo2 >= 50) return 'Excellent';
    if (vo2 >= 40) return 'Good';
    if (vo2 >= 30) return 'Fair';
    return 'Needs Improvement';
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

    // Filter out invalid VO2 data
    const validVO2Data = data.filter(d => d.vo2_estimate !== null && d.vo2_estimate > 0);
    if (validVO2Data.length === 0) return null;

    const vo2Values = validVO2Data.map(d => d.vo2_estimate!);
    const maxVO2 = Math.max(...vo2Values);
    const minVO2 = Math.min(...vo2Values);
    const avgVO2 = vo2Values.reduce((sum, vo2) => sum + vo2, 0) / vo2Values.length;

    // Calculate VO2 range for normalization
    const vo2Range = maxVO2 - minVO2;

    return {
      maxVO2,
      minVO2,
      avgVO2,
      vo2Range,
      validVO2Data,
      vo2Values
    };
  }, [data]);

  if (!chartData) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
        {showHeader && <h3 className="text-xl font-bold text-gray-900 mb-4">{title}</h3>}
        <div className="text-center py-12 text-gray-400">
          <div className="text-5xl mb-4 opacity-50">💪</div>
          <p className="text-lg font-medium">No VO2 Max data available</p>
          <p className="text-sm mt-2">Complete qualifying runs (≥2 miles, ≥12 min) to see VO2 estimates</p>
        </div>
      </div>
    );
  }

  const { maxVO2, minVO2, avgVO2, vo2Range } = chartData;

  const helpContent = {
    title: "VO2 Max Estimate",
    quickTip: "Higher VO2 Max means your body can use oxygen more efficiently, which equals better endurance!",
    detailedExplanation: {
      why: "VO2 Max measures your cardiovascular fitness. It's the maximum oxygen your body can use during intense exercise.",
      benefits: [
        "Track fitness improvements over time",
        "Predict race performance potential",
        "Guide training intensity zones"
      ],
      tips: [
        "Consistency matters more than single data points",
        "Track trends over 4-8 weeks for meaningful insights",
        "Higher isn't always better - focus on steady improvement"
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
              Units: VO2
            </div>
          </div>
        </div>
      )}

      <div className="relative">
        {(() => {
          // Calculate the total height needed for the chart container
          const totalHeight = calculateChartContainerHeight(data, (week) => {
            const vo2Value = week.vo2_estimate;
            if (!vo2Value || vo2Value <= 0) return 0;

            // Use the same calculation as the actual bars
            const normalizedVO2 = vo2Range > 0 ? (vo2Value - minVO2) / vo2Range : 0.5;
            return Math.max(normalizedVO2 * 120 + 40, 40);
          }, CHART_LAYOUT.NUMBER_PADDING_TOP);

          return (
            <div style={getChartContainerStyle(totalHeight)}>
              {data.map((week, index) => {
                const vo2Value = week.vo2_estimate;

            // Skip rendering if no valid VO2 data
            if (!vo2Value || vo2Value <= 0) {
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
                </div>
              );
            }

            // Normalize VO2 value to bar height
            const normalizedVO2 = vo2Range > 0 ? (vo2Value - minVO2) / vo2Range : 0.5;
            const heightPixels = Math.max(normalizedVO2 * 120 + 40, 40);
            const isCurrentWeek = index === 0;

            return (
              <div key={index} className={CHART_BASE_CLASSES.BAR_CONTAINER}>
                {/* VO2 value above bar */}
                <div className={getNumberDisplayClasses('medium')}>
                  {formatChartNumber(vo2Value, 'vo2')}
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

        {/* Centralized Tooltip */}
        <ChartTooltip
          isVisible={hoveredBar !== null}
          position={hoveredBar ? { x: hoveredBar.x, y: hoveredBar.y } : { x: 0, y: 0 }}
          data={{
            week: hoveredBar ? data[hoveredBar.index].week : '',
            value: hoveredBar ? (data[hoveredBar.index].vo2_estimate || 0) : 0,
            unit: 'VO2',
            runs: hoveredBar ? data[hoveredBar.index].runs : undefined,
            distance: hoveredBar ? data[hoveredBar.index].distance : undefined,
            trend: hoveredBar && hoveredBar.index < data.length - 1 && data[hoveredBar.index].vo2_estimate && data[hoveredBar.index + 1].vo2_estimate ?
              (data[hoveredBar.index].vo2_estimate > data[hoveredBar.index + 1].vo2_estimate ? 'improving' :
               data[hoveredBar.index].vo2_estimate < data[hoveredBar.index + 1].vo2_estimate ? 'declining' : 'stable') :
              undefined,
            changePct: hoveredBar && hoveredBar.index < data.length - 1 && data[hoveredBar.index].vo2_estimate && data[hoveredBar.index + 1].vo2_estimate ?
              ((data[hoveredBar.index].vo2_estimate - data[hoveredBar.index + 1].vo2_estimate) / data[hoveredBar.index + 1].vo2_estimate) * 100 :
              undefined,
            additionalInfo: hoveredBar && data[hoveredBar.index].vo2_estimate ? (
              <div className="flex items-center justify-between">
                <span className="text-gray-300 font-medium">Fitness Level:</span>
                <span className={`font-semibold ${
                  data[hoveredBar.index].vo2_estimate >= 50 ? 'text-green-400' :
                  data[hoveredBar.index].vo2_estimate >= 40 ? 'text-blue-400' :
                  data[hoveredBar.index].vo2_estimate >= 30 ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {getFitnessLevel(data[hoveredBar.index].vo2_estimate)}
                </span>
              </div>
            ) : undefined
          }}
        />
      </div>
    </div>
  );
}
