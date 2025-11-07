import React, { useMemo, useState } from 'react';
import { getChartContainerStyle } from '../../hooks/useChartStyles';
import { calculateChartContainerHeight } from '../../utils/chartHelpers';
import { CHART_LAYOUT, CHART_BASE_CLASSES } from '../../utils/chartUtils';
import { useScrollHideTooltip } from '../../hooks/useScrollHideTooltip';

interface WeeklyHRZoneData {
  week: string;
  zone_1: number;
  zone_2: number;
  zone_3: number;
  zone_4: number;
  zone_5: number;
}

interface WeeklyHeartRateChartProps {
  data: WeeklyHRZoneData[];
  title?: string;
}

export default function WeeklyHeartRateChart({ data, title = "Weekly Heart Rate Zones" }: WeeklyHeartRateChartProps) {
  const [hoveredBar, setHoveredBar] = useState<{ index: number; x: number; y: number } | null>(null);

  // Centralized tooltip behavior - hide on scroll
  useScrollHideTooltip(hoveredBar !== null, () => setHoveredBar(null));

  // Memoize calculations for better performance
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    return data;
  }, [data]);

  if (!chartData) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-4">{title}</h3>
        <div className="text-center py-12 text-gray-400">
          <div className="text-5xl mb-4 opacity-50">💓</div>
          <p className="text-lg font-medium">No heart rate data available</p>
          <p className="text-sm mt-2">Complete a few weeks of training to see heart rate trends</p>
        </div>
      </div>
    );
  }

  // Zone colors (same as existing HR chart)
  const zoneColors = {
    zone_1: '#3B82F6', // Blue - Recovery
    zone_2: '#10B981', // Green - Aerobic Base
    zone_3: '#F59E0B', // Orange - Tempo
    zone_4: '#DC2626', // Red - Threshold
    zone_5: '#8B5CF6'  // Purple - VO2 Max
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-xl font-bold text-gray-900">{title}</h3>
        <span className="text-sm font-medium text-purple-600 bg-purple-50 px-3 py-1 rounded-full">
        </span>
      </div>

      {/* Chart */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-4">
          <h4 className="text-sm font-semibold text-gray-700">Weekly HR Zone Distribution</h4>
          <span className="text-xs text-gray-500"></span>
        </div>

        {/* Y-axis scale */}
        <div className="relative mb-2">
          <div className="absolute left-0 top-0 h-32 flex flex-col justify-between text-xs text-gray-400">
            <span>100%</span>
            <span>75%</span>
            <span>50%</span>
            <span>25%</span>
            <span>0%</span>
          </div>
        </div>

        <div className="relative">
          {(() => {
            const maxTotal = Math.max(...data.map(w => w.zone_1 + w.zone_2 + w.zone_3 + w.zone_4 + w.zone_5));

            // Calculate the total height needed for the chart container
            const totalHeight = calculateChartContainerHeight(data, (week) => {
              const totalZones = week.zone_1 + week.zone_2 + week.zone_3 + week.zone_4 + week.zone_5;
              const heightPercentage = maxTotal > 0 ? (totalZones / maxTotal) : 0;
              return Math.max(heightPercentage * 120 + 40, 40);
            }, CHART_LAYOUT.NUMBER_PADDING_TOP);

            return (
              <div style={getChartContainerStyle(totalHeight)}>
                {data.map((week, index) => {
                  const totalZones = week.zone_1 + week.zone_2 + week.zone_3 + week.zone_4 + week.zone_5;
                  // Use same height calculation as WeeklyTrendChart
                  const maxTotal = Math.max(...data.map(w => w.zone_1 + w.zone_2 + w.zone_3 + w.zone_4 + w.zone_5));
                  const heightPercentage = maxTotal > 0 ? (totalZones / maxTotal) : 0;
                  const heightPixels = Math.max(heightPercentage * 120 + 40, 40);

              return (
                <div key={index} className={CHART_BASE_CLASSES.BAR_CONTAINER}>
                  <div
                    className={`${CHART_BASE_CLASSES.BAR} overflow-hidden`}
                  style={{
                    height: `${heightPixels}px`,
                    minWidth: '12px',
                    width: '100%',
                      transition: 'all 0.075s cubic-bezier(0.4, 0, 0.2, 1)'
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
                  >
                    {/* Stacked zones from bottom to top - Zone 1 at bottom, Zone 5 at top */}
                    {/* Zone 1 (Recovery) - Bottom */}
                    <div
                      className="absolute bottom-0 w-full"
                      style={{
                        height: `${(week.zone_1 / totalZones) * 100}%`,
                        backgroundColor: zoneColors.zone_1,
                        minHeight: week.zone_1 > 0 ? '2px' : '0px'
                      }}
                    />
                    {/* Zone 2 (Aerobic Base) */}
                    <div
                      className="absolute w-full"
                      style={{
                        bottom: `${(week.zone_1 / totalZones) * 100}%`,
                        height: `${(week.zone_2 / totalZones) * 100}%`,
                        backgroundColor: zoneColors.zone_2,
                        minHeight: week.zone_2 > 0 ? '2px' : '0px'
                      }}
                    />
                    {/* Zone 3 (Tempo) */}
                    <div
                      className="absolute w-full"
                      style={{
                        bottom: `${((week.zone_1 + week.zone_2) / totalZones) * 100}%`,
                        height: `${(week.zone_3 / totalZones) * 100}%`,
                        backgroundColor: zoneColors.zone_3,
                        minHeight: week.zone_3 > 0 ? '2px' : '0px'
                      }}
                    />
                    {/* Zone 4 (Threshold) */}
                    <div
                      className="absolute w-full"
                      style={{
                        bottom: `${((week.zone_1 + week.zone_2 + week.zone_3) / totalZones) * 100}%`,
                        height: `${(week.zone_4 / totalZones) * 100}%`,
                        backgroundColor: zoneColors.zone_4,
                        minHeight: week.zone_4 > 0 ? '2px' : '0px'
                      }}
                    />
                    {/* Zone 5 (VO2 Max) - Top */}
                    <div
                      className="absolute w-full rounded-t-lg"
                      style={{
                        bottom: `${((week.zone_1 + week.zone_2 + week.zone_3 + week.zone_4) / totalZones) * 100}%`,
                        height: `${(week.zone_5 / totalZones) * 100}%`,
                        backgroundColor: zoneColors.zone_5,
                        minHeight: week.zone_5 > 0 ? '2px' : '0px'
                      }}
                    />
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
                  {new Date(data[hoveredBar.index].week + 'T00:00:00').toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric'
                  })}
                </div>
                <div className="text-xs space-y-1 mt-1">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: zoneColors.zone_1 }}></div>
                    <span>Z1: {data[hoveredBar.index].zone_1.toFixed(1)}%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: zoneColors.zone_2 }}></div>
                    <span>Z2: {data[hoveredBar.index].zone_2.toFixed(1)}%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: zoneColors.zone_3 }}></div>
                    <span>Z3: {data[hoveredBar.index].zone_3.toFixed(1)}%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: zoneColors.zone_4 }}></div>
                    <span>Z4: {data[hoveredBar.index].zone_4.toFixed(1)}%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: zoneColors.zone_5 }}></div>
                    <span>Z5: {data[hoveredBar.index].zone_5.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
              {/* Arrow pointing down */}
              <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-3 border-r-3 border-t-3 border-transparent border-t-gray-800"></div>
            </div>
          )}
        </div>
      </div>

      {/* Zone Legend */}
      <div className="grid grid-cols-5 gap-2 pt-6 border-t border-gray-100">
        {Object.entries(zoneColors).map(([zone, color]) => (
          <div key={zone} className="text-center">
            <div
              className="w-full h-3 rounded mb-1"
              style={{ backgroundColor: color }}
            />
            <div className="text-xs text-gray-600 font-medium">
              {zone.replace('zone_', 'Z')}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
