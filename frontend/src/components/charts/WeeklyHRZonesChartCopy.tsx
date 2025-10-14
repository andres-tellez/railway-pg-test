import React, { useMemo, useState } from 'react';
import ChartHelpTooltip from './ChartHelpTooltip';
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

interface WeeklyHRZonesChartProps {
  data: WeeklyHRZoneData[];
  title?: string;
}

export default function WeeklyHRZonesChart({
  data,
  title = "HR Zones"
}: WeeklyHRZonesChartProps) {
  const [hoveredBar, setHoveredBar] = useState<{ index: number; x: number; y: number } | null>(null);

  // Centralized tooltip behavior - hide on scroll
  useScrollHideTooltip(hoveredBar !== null, () => setHoveredBar(null));

  // Zone colors (defined outside the map for reuse)
  // Helper function to format dates as M/D
  const formatDate = (dateStr: string): string => {
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
  };

  const zoneColors = {
    zone_1: '#3B82F6', // Blue - Recovery
    zone_2: '#10B981', // Green - Aerobic Base
    zone_3: '#F59E0B', // Orange - Tempo
    zone_4: '#EF4444', // Red - Threshold
    zone_5: '#8B5CF6'  // Purple - VO2 Max
  };

  // Memoize calculations for better performance
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    const maxTotal = Math.max(...data.map(w => w.zone_1 + w.zone_2 + w.zone_3 + w.zone_4 + w.zone_5));

    return { maxTotal };
  }, [data]);

  if (!chartData) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-4">{title}</h3>
        <div className="text-center py-12 text-gray-400">
          <div className="text-5xl mb-4 opacity-50">❤️</div>
          <p className="text-lg font-medium">No HR zone data available</p>
          <p className="text-sm mt-2">Complete runs with heart rate data to see zone distribution</p>
        </div>
      </div>
    );
  }

  const { maxTotal } = chartData;

  const helpContent = {
    title: "Heart Rate Zones",
    quickTip: "Most time in easy zones (1-2), some time in hard zones (3-5) for optimal training!",
    detailedExplanation: {
      why: "Different heart rate zones train different energy systems. Proper distribution prevents overtraining.",
      benefits: [
        "Trains the right energy systems",
        "Prevents overtraining and burnout",
        "Tracks fitness improvements"
      ],
      tips: [
        "80% time in Zones 1-2 (easy/recovery)",
        "20% time in Zones 3-5 (tempo/threshold)",
        "High HR at easy pace = need more recovery"
      ]
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100 relative">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-3">
          <h3 className="text-xl font-bold text-gray-900">{title}</h3>
          <ChartHelpTooltip helpContent={helpContent} position="top-right" />
        </div>
        <div className="text-right">
          <div className="text-lg text-gray-700">
            Units: %
          </div>
        </div>
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
          // Calculate the total height needed for the chart container
          const totalHeight = calculateChartContainerHeight(data, (week) => {
            const totalZones = week.zone_1 + week.zone_2 + week.zone_3 + week.zone_4 + week.zone_5;
            const heightPercentage = maxTotal > 0 ? (totalZones / maxTotal) : 0;
            return heightPercentage * CHART_LAYOUT.MAX_HEIGHT_PX;
          }, CHART_LAYOUT.NUMBER_PADDING_TOP);

          return (
            <div style={getChartContainerStyle(totalHeight)}>
              {data.map((week, index) => {
                const totalZones = week.zone_1 + week.zone_2 + week.zone_3 + week.zone_4 + week.zone_5;
                const heightPercentage = maxTotal > 0 ? (totalZones / maxTotal) : 0;
            const heightPixels = Math.max(heightPercentage * 120 + 40, 40);

            return (
              <div key={index} className={CHART_BASE_CLASSES.BAR_CONTAINER}>
                {/* The stacked bar */}
                <div
                  className="chart-bar"
                  style={{
                    height: `${heightPixels}px`,
                    minWidth: '12px'
                  }}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setHoveredBar({
                      index,
                      x: rect.left + rect.width / 2,
                      y: rect.top
                    });
                  }}
                  onMouseLeave={() => setHoveredBar(null)}
                >
                  {/* Stacked zones from bottom to top - Zone 1 at bottom, Zone 5 at top */}
                  {/* Zone 1 (Recovery) - Bottom */}
                  <div
                    className="absolute bottom-0"
                    style={{
                      width: '100%',
                      height: `${(week.zone_1 / totalZones) * 100}%`,
                      backgroundColor: zoneColors.zone_1,
                      minHeight: week.zone_1 > 0 ? '2px' : '0px'
                    }}
                  />
                  {/* Zone 2 (Aerobic Base) */}
                  <div
                    className="absolute"
                    style={{
                      width: '100%',
                      bottom: `${(week.zone_1 / totalZones) * 100}%`,
                      height: `${(week.zone_2 / totalZones) * 100}%`,
                      backgroundColor: zoneColors.zone_2,
                      minHeight: week.zone_2 > 0 ? '2px' : '0px'
                    }}
                  />
                  {/* Zone 3 (Tempo) */}
                  <div
                    className="absolute"
                    style={{
                      width: '100%',
                      bottom: `${((week.zone_1 + week.zone_2) / totalZones) * 100}%`,
                      height: `${(week.zone_3 / totalZones) * 100}%`,
                      backgroundColor: zoneColors.zone_3,
                      minHeight: week.zone_3 > 0 ? '2px' : '0px'
                    }}
                  />
                  {/* Zone 4 (Threshold) */}
                  <div
                    className="absolute"
                    style={{
                      width: '100%',
                      bottom: `${((week.zone_1 + week.zone_2 + week.zone_3) / totalZones) * 100}%`,
                      height: `${(week.zone_4 / totalZones) * 100}%`,
                      backgroundColor: zoneColors.zone_4,
                      minHeight: week.zone_4 > 0 ? '2px' : '0px'
                    }}
                  />
                  {/* Zone 5 (VO2 Max) - Top */}
                  <div
                    className="absolute rounded-t-lg"
                    style={{
                      width: '100%',
                      bottom: `${((week.zone_1 + week.zone_2 + week.zone_3 + week.zone_4) / totalZones) * 100}%`,
                      height: `${(week.zone_5 / totalZones) * 100}%`,
                      backgroundColor: zoneColors.zone_5,
                      minHeight: week.zone_5 > 0 ? '2px' : '0px'
                    }}
                  />
                </div>

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

        {/* Custom Tooltip for HR Zones */}
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
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#3B82F6' }}></div>
                  <span>Z1: {data[hoveredBar.index].zone_1.toFixed(1)}%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#10B981' }}></div>
                  <span>Z2: {data[hoveredBar.index].zone_2.toFixed(1)}%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#F59E0B' }}></div>
                  <span>Z3: {data[hoveredBar.index].zone_3.toFixed(1)}%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#EF4444' }}></div>
                  <span>Z4: {data[hoveredBar.index].zone_4.toFixed(1)}%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#8B5CF6' }}></div>
                  <span>Z5: {data[hoveredBar.index].zone_5.toFixed(1)}%</span>
                </div>
              </div>
            </div>
            {/* Arrow pointing down */}
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-3 border-r-3 border-t-3 border-transparent border-t-gray-800"></div>
          </div>
        )}
      </div>

      {/* Zone Legend - Bottom Right */}
      <div className="flex justify-end pt-6 border-t border-gray-100">
        <div className="flex items-center space-x-4">
          {Object.entries(zoneColors).map(([zone, color]) => (
            <div key={zone} className="flex items-center space-x-2">
              <div
                className="w-4 h-4 rounded-sm"
                style={{ backgroundColor: color }}
              />
              <span className="text-xs text-gray-600 font-medium">
                {zone.replace('zone_', 'Z')}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
