import React, { useMemo, useState } from 'react';
import ChartHelpTooltip from './ChartHelpTooltip';
import { useStaticBarStyle, useBarColorClasses, getChartContainerStyle, getNumberDisplayClasses } from '../../hooks/useChartStyles';
import { getBarShadow, calculateChartContainerHeight, formatChartNumber, calculateBarHeight } from '../../utils/chartHelpers';
import { CHART_SHADOWS, CHART_LAYOUT, CHART_BASE_CLASSES } from '../../utils/chartUtils';
import { useScrollHideTooltip } from '../../hooks/useScrollHideTooltip';

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

interface WeeklyGoalData {
  week: string;
  goal_miles: number;
}

interface TotalMilesActualVsPlanChartProps {
  data: WeeklyTrendData[];
  weeklyGoals?: WeeklyGoalData[];
  title?: string;
  hrZoneData?: WeeklyHRZoneData[];
  showHeader?: boolean;
  helpTooltip?: any;
}

export default function TotalMilesActualVsPlanChart({ data, weeklyGoals = [], title = "Total Miles - Actual vs Plan", hrZoneData, showHeader = true, helpTooltip }: TotalMilesActualVsPlanChartProps) {
  const [hoveredBar, setHoveredBar] = useState<{ index: number; x: number; y: number } | null>(null);

  // Centralized tooltip behavior - hide on scroll
  useScrollHideTooltip(hoveredBar !== null, () => setHoveredBar(null));

  // Use shared getBarShadow function with exceededPlanned option
  const getBarShadowForTotalMiles = (barColor: string, index: number, exceededPlanned: boolean): string => {
    return getBarShadow(barColor, index, { exceededGoal: exceededPlanned });
  };

  // Helper function to find planned total miles for a specific week
  const findPlannedTotalMilesForWeek = (week: string): number | null => {
    // Handle both date formats: '2025-10-06' and '2025-10-06T00:00:00'
    const goal = weeklyGoals.find(g => {
      const goalWeek = g.week;
      // Direct match
      if (goalWeek === week) return true;
      // Match date part only (handle datetime format)
      if (week.includes('T') && goalWeek === week.split('T')[0]) return true;
      if (goalWeek.includes('T') && week === goalWeek.split('T')[0]) return true;
      return false;
    });
    return goal ? goal.goal_miles : null;
  };

  // Use shared memoized static style hook
  const staticBarStyle = useStaticBarStyle();


  // Memoize calculations for better performance
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    // Calculate chart maximum from both actual AND planned miles (whichever is taller)
    const allActualMiles = data.map(d => d.distance);
    const allPlannedMiles = data.map(d => {
      const planned = findPlannedTotalMilesForWeek(d.week);
      return planned || 0;
    });
    const maxDistance = Math.max(...allActualMiles, ...allPlannedMiles, 1);

    // Calculate bar colors based on significant drop logic
    const barColors = data.map((week, index) => {
      if (index === data.length - 1) return 'normal'; // Oldest week, no comparison

      const currentDistance = week.distance;
      const prevDistance = data[index + 1].distance;

      if (prevDistance === 0) return 'normal'; // Avoid division by zero

      const dropPct = ((prevDistance - currentDistance) / prevDistance) * 100;

      // RED FLAG Logic:
      // 1. Single dramatic drop (>40%)
      if (dropPct > 40) return 'significant_drop';

      // 2. Two consecutive drops (current >30% AND previous >15%)
      if (dropPct > 30 && index < data.length - 2) {
        const prevPrevDistance = data[index + 2].distance;
        if (prevPrevDistance > 0) {
          const prevDropPct = ((prevPrevDistance - prevDistance) / prevPrevDistance) * 100;
          if (prevDropPct > 15) return 'significant_drop';
        }
      }

      // Everything else is normal (blue)
      return 'normal';
    });

    // Pre-calculate all bar data to avoid calculations in render loop
    const barData = data.map((week, index) => {
      const heightPixels = calculateBarHeight(week.distance, maxDistance);
      const isCurrentWeek = index === 0;
      const plannedTotalMiles = findPlannedTotalMilesForWeek(week.week);
      const plannedTotalMilesHeightPixels = plannedTotalMiles ?
        calculateBarHeight(plannedTotalMiles, maxDistance) : 0;
      const exceededPlannedTotalMiles = plannedTotalMiles ? week.distance >= plannedTotalMiles : false;
      const barColor = barColors[index];

      return {
        heightPixels,
        isCurrentWeek,
        plannedTotalMiles,
        plannedTotalMilesHeightPixels,
        exceededPlannedTotalMiles,
        barColor
      };
    });

    return { maxDistance, barColors, barData };
  }, [data, weeklyGoals]);

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

  const { maxDistance, barColors } = chartData;

  // Helper function to format date as M/D
  const formatDate = (dateString: string) => {
    try {
      const dateStr = dateString;
      let date;
      if (dateStr.includes('T')) {
        date = new Date(dateStr);
      } else {
        date = new Date(dateStr + 'T00:00:00');
      }
      const month = date.getMonth() + 1; // getMonth() is 0-indexed
      const day = date.getDate();
      return `${month}/${day}`;
    } catch (error) {
      return dateString; // fallback to original string if parsing fails
    }
  };

  // Helper function to get actual total miles bar color classes (using shared logic)
  const getActualTotalMilesBarColorClasses = (colorType: string, isCurrentWeek: boolean) => {
    const baseClasses = CHART_BASE_CLASSES.BAR;
    const currentWeekRing = isCurrentWeek ? 'ring-2 ring-opacity-50' : '';

    // All weeks use their respective colors based on performance
    if (colorType === 'personal_record') return `${baseClasses} bg-green-500 ${currentWeekRing} ring-green-200`;
    if (colorType === 'significant_drop') return `${baseClasses} bg-red-600 ${currentWeekRing} ring-red-200`;
    return `${baseClasses} bg-blue-500 ${currentWeekRing} ring-blue-200`;
  };

  // Zone colors (defined outside the map for reuse)
  const zoneColors = {
    zone_1: '#3B82F6', // Blue - Recovery
    zone_2: '#10B981', // Green - Aerobic Base
    zone_3: '#F59E0B', // Orange - Tempo
    zone_4: '#DC2626', // Red - Threshold
    zone_5: '#8B5CF6'  // Purple - VO2 Max
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
      {showHeader && (
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-bold text-gray-900">{title}</h3>
            {helpTooltip && <ChartHelpTooltip helpContent={helpTooltip} />}
          </div>
          <div className="text-right">
            <div className="text-lg text-gray-700">
              Units: mi
            </div>
          </div>
        </div>
      )}

      {/* Chart */}
      <div>

        <div className="relative">
          {(() => {
            // Calculate the total height needed for the chart container
            const totalHeight = calculateChartContainerHeight(data, (week) => {
              return calculateBarHeight(week.distance, maxDistance);
            }, CHART_LAYOUT.NUMBER_PADDING_TOP);

            return (
              <div style={getChartContainerStyle(totalHeight)}>
                {data.map((week, index) => {
                  const barInfo = chartData.barData[index];
                  const colorClasses = getActualTotalMilesBarColorClasses(barInfo.barColor, barInfo.isCurrentWeek);


              return (
                <div key={index} className={CHART_BASE_CLASSES.BAR_CONTAINER}>
                  {/* Distance Label */}
                  <div className={getNumberDisplayClasses('medium')}>
                    {formatChartNumber(week.distance, 'distance')}
                  </div>

                  {/* Bars container (Actual + Planned side-by-side) */}
                  <div className="relative w-full" style={{ height: `${Math.max(barInfo.heightPixels, barInfo.plannedTotalMilesHeightPixels)}px` }}>
                    {/* Actual Bar (left, wider) */}
                    <div
                      className={colorClasses}
                      style={{
                        ...staticBarStyle,
                        position: 'absolute',
                        left: 0,
                        width: barInfo.plannedTotalMiles ? '62%' : '100%',
                        height: `${barInfo.heightPixels}px`,
                        boxShadow: getBarShadowForTotalMiles(barInfo.barColor, index, barInfo.exceededPlannedTotalMiles)
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

                    {/* Planned Bar (right, thinner) */}
                    {barInfo.plannedTotalMiles && (
                      <div
                        className="absolute right-0 bg-gray-400/70 ring-1 ring-gray-300"
                        style={{
                          borderRadius: '0.5rem 0.5rem 0 0',
                          width: '30%',
                          height: `${barInfo.plannedTotalMilesHeightPixels}px`
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
                        aria-label={`Planned ${barInfo.plannedTotalMiles.toFixed(1)} miles`}
                        role="img"
                      />
                    )}
                  </div>

                  {/* Date Label */}
                  <div className="mt-2 text-center">
                    <div className="text-xs text-gray-500">
                      {formatDate(week.week)}
                    </div>
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
              className="fixed z-50 bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-600 rounded-lg p-3 shadow-2xl pointer-events-none backdrop-blur-sm"
              style={{
                left: `${hoveredBar.x}px`,
                top: `${hoveredBar.y}px`,
                transform: 'translate(-50%, -100%)',
                minWidth: '180px',
                backdropFilter: 'blur(8px)',
              }}
            >
              {(() => {
                const week = data[hoveredBar.index];
                const barInfo = chartData.barData[hoveredBar.index];
                const prevWeek = data[hoveredBar.index + 1];
                const changePct = prevWeek ? ((week.distance - prevWeek.distance) / prevWeek.distance) * 100 : null;

                return (
                  <>
                    <div className="text-white font-bold text-sm mb-2 text-center bg-gray-700/30 rounded px-2 py-1">
                      Wk of {(() => {
                        try {
                          const dateStr = week.week;
                          if (dateStr.includes('T')) {
                            return new Date(dateStr).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric'
                            });
                          } else {
                            return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric'
                            });
                          }
                        } catch (error) {
                          return week.week;
                        }
                      })()}
                    </div>
                    <div className="space-y-1.5 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300">Actual:</span>
                        <span className="text-white font-semibold">{week.distance.toFixed(1)} mi</span>
                      </div>
                      {barInfo.plannedTotalMiles && (
                        <div className="flex items-center justify-between">
                          <span className="text-gray-300">Planned:</span>
                          <span className="text-white font-semibold">{barInfo.plannedTotalMiles.toFixed(1)}</span>
                        </div>
                      )}
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300">Runs:</span>
                        <span className="text-white font-semibold">{week.runs}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300">Pace:</span>
                        <span className="text-white font-semibold">{week.avgPace}</span>
                      </div>
                      {changePct !== null && (
                        <div className="flex items-center justify-between">
                          <span className="text-gray-300">vs Last:</span>
                          <span className={`font-bold text-sm ${changePct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {changePct >= 0 ? '+' : ''}{changePct.toFixed(1)}%
                          </span>
                        </div>
                      )}
                      {barInfo.exceededPlannedTotalMiles && (
                        <div className="mt-2 pt-2 border-t border-gray-600 text-green-400 font-bold text-center text-sm bg-green-900/20 rounded px-2 py-1">
                          🎯 Goal Achieved!
                        </div>
                      )}
                      {barInfo.plannedTotalMiles && !barInfo.exceededPlannedTotalMiles && (
                        <div className="mt-2 pt-2 border-t border-gray-600 text-orange-400 font-semibold text-center text-sm bg-orange-900/20 rounded px-2 py-1">
                          Planned: {barInfo.plannedTotalMiles.toFixed(1)}
                        </div>
                      )}
                      {barInfo.barColor === 'significant_drop' && (
                        <div className="mt-2 pt-2 border-t border-gray-600 text-red-400 font-bold text-center text-sm bg-red-900/20 rounded px-2 py-1">
                          ⚠️ Significant Drop
                        </div>
                      )}
                    </div>
                  </>
                );
              })()}
            </div>
          )}
        </div>

        {/* Legend positioned below bars on the right */}
        <div className="flex justify-end mt-4">
          <div className="flex gap-6 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-blue-400 rounded"></div>
              <span>Actual</span>
            </div>
            {weeklyGoals && weeklyGoals.length > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-gray-400 rounded ring-1 ring-gray-300"></div>
                <span>Planned</span>
              </div>
            )}
            <div className="flex items-center gap-2 relative group">
              <div className="w-4 h-4 bg-red-600 rounded"></div>
              <span>Significant Drop</span>
              <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-72 bg-gray-900 border border-gray-600 rounded-lg p-3 text-xs text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                <strong>Significant Drop:</strong> Red flags indicate concerning patterns:<br/>
                • Two consecutive weeks dropping &gt;30% and &gt;15%<br/>
                • Single week dropping &gt;40%<br/>
                <br/>
                <em>Note: Intentional race tapers (single-week drops) typically won't trigger this</em>
              </div>
            </div>
          </div>
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
                  <div key={index} style={{
                    flex: '1 1 0',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'flex-end',
                    minWidth: 0
                  }}>
                    <div
                      className=""
                      style={{
                        height: `${heightPixels}px`,
                        width: '100%',
                        borderRadius: '0.5rem 0.5rem 0 0',
                        transition: 'all 0.075s cubic-bezier(0.4, 0, 0.2, 1)',
                        cursor: 'pointer',
                        position: 'relative',
                        overflow: 'hidden'
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
                <div className={CHART_BASE_CLASSES.TOOLTIP_CONTAINER}>
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
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#DC2626' }}></div>
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
