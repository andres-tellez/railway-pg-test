import React, { useMemo, useState } from 'react';
import ChartHelpTooltip from './ChartHelpTooltip';

interface WeeklyTrendData {
  week: string;
  distance: number;
  runs: number;
  avgPace: string;
}

interface WeeklyHRZoneData {
  week: string;
  zone_1: number;
  zone_2: number;
  zone_3: number;
  zone_4: number;
  zone_5: number;
}

interface WeeklyTrendChartProps {
  data: WeeklyTrendData[];
  title?: string;
  totalMiles?: number;
  avgWeeklyMiles?: number;
  hrZoneData?: WeeklyHRZoneData[];
  showHeader?: boolean;
  helpTooltip?: any;
}

export default function WeeklyTrendChart({ data, title = "Weekly Current Trends", totalMiles, avgWeeklyMiles, hrZoneData, showHeader = true, helpTooltip }: WeeklyTrendChartProps) {
  const [hoveredBar, setHoveredBar] = useState<{ index: number; x: number; y: number } | null>(null);

  // Memoize calculations for better performance
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    const maxDistance = Math.max(...data.map(d => d.distance), 1);
    const totalDistance = data.reduce((sum, week) => sum + week.distance, 0);
    const avgWeekly = totalDistance / data.length;

    return { maxDistance, totalDistance, avgWeekly };
  }, [data]);

  if (!chartData) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
        {showHeader && <h3 className="text-xl font-bold text-gray-900 mb-4">{title}</h3>}
        <div className="text-center py-12 text-gray-400">
          <div className="text-5xl mb-4 opacity-50">📈</div>
          <p className="text-lg font-medium">No trend data available</p>
          <p className="text-sm mt-2">Complete a few weeks of training to see trends</p>
        </div>
      </div>
    );
  }

  const { maxDistance, totalDistance, avgWeekly } = chartData;

  // Zone colors (defined outside the map for reuse)
  const zoneColors = {
    zone_1: '#3B82F6', // Blue - Recovery
    zone_2: '#10B981', // Green - Aerobic Base
    zone_3: '#F59E0B', // Orange - Tempo
    zone_4: '#EF4444', // Red - Threshold
    zone_5: '#8B5CF6'  // Purple - VO2 Max
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
      {showHeader && (
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-bold text-gray-900">{title}</h3>
          <span className="text-sm font-medium text-blue-600 bg-blue-50 px-3 py-1 rounded-full">
          </span>
        </div>
      )}

      {/* Chart */}
      <div>
        <div className="flex items-center gap-3 mb-6">
          <h3 className="text-xl font-bold text-gray-900">Weekly Distance</h3>
          {helpTooltip && <ChartHelpTooltip helpContent={helpTooltip} />}
        </div>

        <div className="relative">
          <div className="flex items-end space-x-1 h-48 bg-gradient-to-t from-gray-50 to-white p-6 rounded-xl border border-gray-100">
            {data.map((week, index) => {
              const heightPercentage = maxDistance > 0 ? (week.distance / maxDistance) : 0;
              const heightPixels = Math.max(heightPercentage * 120 + 40, 40);
              const isCurrentWeek = index === 0;

              return (
                <div key={index} className="flex flex-col items-center justify-end flex-1 min-w-0 group">
                  <div
                    className={`w-full max-w-10 rounded-t-lg transition-all duration-75 cursor-pointer relative bg-gradient-to-t from-blue-500 to-blue-400 hover:from-blue-600 hover:to-blue-500 hover:scale-105 hover:shadow-lg ${isCurrentWeek ? 'ring-2 ring-blue-200 ring-opacity-50' : ''}`}
                    style={{
                      height: `${heightPixels}px`,
                      minWidth: '12px',
                      boxShadow: '0 2px 8px rgba(59, 130, 246, 0.2)',
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
                  />
                </div>
              );
            })}
          </div>

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
              <div className="flex flex-col items-center">
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
                  {data[hoveredBar.index].distance.toFixed(1)} mi
                </div>
              </div>
              {/* Arrow pointing down */}
              <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-3 border-r-3 border-t-3 border-transparent border-t-gray-800"></div>
            </div>
          )}
        </div>
      </div>

      {/* HR Zone Chart Section */}
      {hrZoneData && hrZoneData.length > 0 && (
        <div className="mt-8">
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
            <div className="flex items-end space-x-1 h-48 bg-gradient-to-t from-gray-50 to-white p-6 rounded-xl border border-gray-100">
              {hrZoneData.map((week, index) => {
                const totalZones = week.zone_1 + week.zone_2 + week.zone_3 + week.zone_4 + week.zone_5;
                // Use same height calculation as distance chart
                const maxTotal = Math.max(...hrZoneData.map(w => w.zone_1 + w.zone_2 + w.zone_3 + w.zone_4 + w.zone_5));
                const heightPercentage = maxTotal > 0 ? (totalZones / maxTotal) : 0;
                const heightPixels = Math.max(heightPercentage * 120 + 40, 40);

                return (
                  <div key={index} className="flex flex-col items-center justify-end flex-1 min-w-0 group">
                    <div
                      className="w-full max-w-10 rounded-t-lg transition-all duration-75 cursor-pointer relative hover:scale-105 hover:shadow-lg overflow-hidden"
                      style={{
                        height: `${heightPixels}px`,
                        minWidth: '12px',
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
                <div className="flex flex-col items-center">
                  <div>
                    {new Date(hrZoneData[hoveredBar.index].week + 'T00:00:00').toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric'
                    })}
                  </div>
                  <div className="text-xs space-y-1 mt-1">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#3B82F6' }}></div>
                      <span>Z1: {hrZoneData[hoveredBar.index].zone_1.toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#10B981' }}></div>
                      <span>Z2: {hrZoneData[hoveredBar.index].zone_2.toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#F59E0B' }}></div>
                      <span>Z3: {hrZoneData[hoveredBar.index].zone_3.toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#EF4444' }}></div>
                      <span>Z4: {hrZoneData[hoveredBar.index].zone_4.toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#8B5CF6' }}></div>
                      <span>Z5: {hrZoneData[hoveredBar.index].zone_5.toFixed(1)}%</span>
                    </div>
                  </div>
                </div>
                {/* Arrow pointing down */}
                <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-3 border-r-3 border-t-3 border-transparent border-t-gray-800"></div>
              </div>
            )}
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
      )}

    </div>
  );
}
