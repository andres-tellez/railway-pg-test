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

interface WeeklyGoalData {
  week: string;
  goal_miles: number;
}

interface WeeklyTrendChartProps {
  data: WeeklyTrendData[];
  weeklyGoals?: WeeklyGoalData[];
  title?: string;
  hrZoneData?: WeeklyHRZoneData[];
  showHeader?: boolean;
  helpTooltip?: any;
}

export default function WeeklyTrendChart({ data, weeklyGoals = [], title = "Weekly Distance - Plan vs Actual", hrZoneData, showHeader = true, helpTooltip }: WeeklyTrendChartProps) {
  const [hoveredBar, setHoveredBar] = useState<{ index: number; x: number; y: number } | null>(null);

  // Helper function to find goal for a specific week
  const findGoalForWeek = (week: string): number | null => {
    // Extract just the date part (YYYY-MM-DD) from the week string
    const dateOnly = week.split('T')[0];

    console.log(`[DEBUG] Looking for goal for week ${week} (dateOnly: ${dateOnly})`);
    console.log(`[DEBUG] Available goals:`, weeklyGoals.map(g => ({ week: g.week, goal_miles: g.goal_miles })));

    // Try exact match first
    let goal = weeklyGoals.find(g => g.week === dateOnly);

    if (!goal) {
      // If no exact match, try to find goal by matching the week pattern
      // The issue is that goals might be in 2026 while trends are in 2025
      // Try converting 2026 dates to 2025 dates by subtracting 1 year
      const goalWithAdjustedYear = weeklyGoals.find(g => {
        if (g.week && g.week.includes('2026')) {
          const adjustedDate = g.week.replace('2026', '2025');
          console.log(`[DEBUG] Trying 2026->2025: ${g.week} -> ${adjustedDate} vs ${dateOnly}`);
          return adjustedDate === dateOnly;
        }
        return false;
      });

      if (goalWithAdjustedYear) {
        goal = goalWithAdjustedYear;
        console.log(`[DEBUG] Found goal with year adjustment: ${goal.week} -> matches ${dateOnly}`);
      }
    }

    // If still no match, try the reverse - convert 2025 trend dates to 2026 to match goals
    if (!goal) {
      const goalWithReverseAdjustment = weeklyGoals.find(g => {
        if (g.week && g.week.includes('2026') && dateOnly.includes('2025')) {
          const trendDateTo2026 = dateOnly.replace('2025', '2026');
          const goalDateOnly = g.week.split('T')[0];
          console.log(`[DEBUG] Trying reverse 2025->2026: ${dateOnly} -> ${trendDateTo2026} vs ${goalDateOnly}`);
          return goalDateOnly === trendDateTo2026;
        }
        return false;
      });

      if (goalWithReverseAdjustment) {
        goal = goalWithReverseAdjustment;
        console.log(`[DEBUG] Found goal with reverse adjustment: ${goal.week} -> matches ${dateOnly}`);
      }
    }

    // If still no match, try to match by array position
    // This handles cases where the goals and trends are in the same order but different years
    if (!goal && weeklyGoals.length > 0) {
      console.log(`[DEBUG] No year adjustment match found, trying position-based matching`);

      // Find the index of the current week in the trends data
      const trendIndex = data.findIndex(trend => trend.week === week);
      console.log(`[DEBUG] Trend index: ${trendIndex}, Weekly goals length: ${weeklyGoals.length}`);

      if (trendIndex >= 0 && trendIndex < weeklyGoals.length) {
        goal = weeklyGoals[trendIndex];
        console.log(`[DEBUG] Found goal by position: index ${trendIndex} -> ${goal.week} (${goal.goal_miles} miles)`);
      } else {
        console.log(`[DEBUG] Position-based matching failed: trendIndex=${trendIndex}, goalsLength=${weeklyGoals.length}`);
      }
    }

    console.log(`[DEBUG] Final goal match:`, goal);
    return goal ? goal.goal_miles : null;
  };

  // Debug logging
  console.log(`[DEBUG] WeeklyTrendChart received weeklyGoals:`, weeklyGoals);
  console.log(`[DEBUG] First few weeklyGoals:`, weeklyGoals.slice(0, 3));
  console.log(`[DEBUG] Weekly trends data:`, data);
  console.log(`[DEBUG] First few weekly trends:`, data.slice(0, 3));

  // Memoize calculations for better performance
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    const maxDistance = Math.max(...data.map(d => d.distance), 1);

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

    return { maxDistance, barColors };
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

  // Helper function to get bar color classes
                const getBarColorClasses = (colorType: string, isCurrentWeek: boolean) => {
                const baseClasses = 'w-full rounded-t-lg transition-all duration-75 cursor-pointer relative hover:scale-105 hover:shadow-lg';
                const currentWeekRing = isCurrentWeek ? 'ring-2 ring-opacity-50' : '';

                if (colorType === 'significant_drop') {
                  return `${baseClasses} bg-red-500 ${currentWeekRing} ring-red-200`;
                }

                // Default: blue for normal
                return `${baseClasses} bg-blue-500 ${currentWeekRing} ring-blue-200`;
              };

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
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-bold text-gray-900">{title}</h3>
            {helpTooltip && <ChartHelpTooltip helpContent={helpTooltip} />}
          </div>
        </div>
      )}

      {/* Chart */}
      <div>

        <div className="relative">
          <div className="flex items-end space-x-1 h-48 bg-gradient-to-t from-gray-100 to-gray-50 p-6 rounded-xl">
            {data.map((week, index) => {
              const heightPercentage = maxDistance > 0 ? (week.distance / maxDistance) : 0;
              const heightPixels = heightPercentage * 140;
              const isCurrentWeek = index === 0;

              // Get goal for this week from training plan data
              const goalMiles = findGoalForWeek(week.week);
              const goalHeightPercentage = goalMiles && maxDistance > 0 ? (goalMiles / maxDistance) : 0;
              // Make goal height proportional to the actual bar height
              const goalHeightPixels = goalMiles ? (goalMiles / week.distance) * heightPixels : 0;

              const exceededGoal = goalMiles ? week.distance >= goalMiles : false;

              const barColor = barColors[index];
              const colorClasses = getBarColorClasses(barColor, isCurrentWeek);

              // Debug logging for each bar
              if (goalMiles) {
                console.log(`[DEBUG] Bar ${index} (${week.week}): goal=${goalMiles}, actual=${week.distance}, exceeded=${exceededGoal}`);
              }

              return (
                <div key={index} className="flex flex-col items-center justify-end flex-1 min-w-0 group relative">
                  {/* Actual Bar */}
                  <div
                    className={colorClasses}
                    style={{
                      height: `${heightPixels}px`,
                      boxShadow: barColor === 'significant_drop'
                        ? '0 2px 8px rgba(239, 68, 68, 0.3)'
                        : exceededGoal
                        ? '0 2px 8px rgba(34, 197, 94, 0.3)'
                        : '0 2px 8px rgba(59, 130, 246, 0.2)',
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
                    {/* Distance Label */}
                    <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-sm font-semibold whitespace-nowrap text-gray-700">
                      {week.distance.toFixed(1)}
                    </div>

                    {/* OPTION 2: Subtle Goal Zone with Better Visual Hierarchy */}
                    {/* Very light black opaque shade from goal line to bottom - only render if goal exists and is within bar */}
                    {goalMiles && goalHeightPixels > 0 && goalHeightPixels <= heightPixels && (
                      <div
                        className="absolute left-0 right-0"
                        style={{
                          bottom: '0px',
                          height: `${goalHeightPixels}px`,
                          background: 'rgba(0, 0, 0, 0.25)', // Darker black opaque shade below the line
                          zIndex: 1
                        }}
                      />
                    )}

                    {/* Gradient goal line - darkest at top, fades to transparent at bottom - only render if goal exists */}
                    {goalMiles && goalHeightPixels > 0 && goalHeightPixels <= heightPixels && (
                      <div
                        className="absolute left-0 right-0 z-10"
                        style={{
                          bottom: `${goalHeightPixels}px`,
                          height: '10px',
                          background: 'linear-gradient(to bottom, rgba(0,0,0,0.8), rgba(0,0,0,0.4), rgba(0,0,0,0.25))',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                          zIndex: 10
                        }}
                      />
                    )}

                    {/* Goal Target Line (when goal is above bar) */}
                    {goalMiles && goalHeightPixels > heightPixels && (
                      <div
                        className="absolute left-0 right-0 border-t-3 border-dashed border-gray-700 z-10"
                        style={{
                          bottom: `${goalHeightPixels}px`,
                          transform: 'translateY(-2px)',
                          boxShadow: '0 0 6px rgba(0,0,0,0.3)',
                          zIndex: 10
                        }}
                      />
                    )}

                    {/* OPTION B: No Background, Just Text - Centered between bottom of bar and goal line */}
                    {goalMiles && (
                      <div className="absolute left-1/2 transform -translate-x-1/2 text-sm font-normal text-white"
                           style={{
                             bottom: `${goalHeightPixels / 2}px`,
                             textShadow: '1px 1px 2px rgba(0,0,0,0.8), -1px -1px 2px rgba(0,0,0,0.8)',
                             zIndex: 15
                           }}>
                        {goalMiles} mi
                      </div>
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
                const goalMiles = findGoalForWeek(week.week);
                const prevWeek = data[hoveredBar.index + 1];
                const changePct = prevWeek ? ((week.distance - prevWeek.distance) / prevWeek.distance) * 100 : null;
                const exceededGoal = goalMiles ? week.distance >= goalMiles : null;

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
                      {goalMiles && (
                        <div className="flex items-center justify-between">
                          <span className="text-gray-300">Goal:</span>
                          <span className="text-white font-semibold">{goalMiles.toFixed(1)} mi</span>
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
                      {exceededGoal !== null && exceededGoal && (
                        <div className="mt-2 pt-2 border-t border-gray-600 text-green-400 font-bold text-center text-sm bg-green-900/20 rounded px-2 py-1">
                          🎯 Goal Achieved!
                        </div>
                      )}
                      {exceededGoal !== null && !exceededGoal && (
                        <div className="mt-2 pt-2 border-t border-gray-600 text-orange-400 font-semibold text-center text-sm bg-orange-900/20 rounded px-2 py-1">
                          Goal: {goalMiles?.toFixed(1)} mi
                        </div>
                      )}
                      {barColors[hoveredBar.index] === 'significant_drop' && (
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
            <div className="flex items-center gap-2 relative group">
              <div className="w-4 h-4 bg-blue-600 rounded border-2 border-black"></div>
              <span>Plan</span>
              <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-80 bg-gray-900 border border-gray-600 rounded-lg p-3 text-xs text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                <strong>Training Plan Goal:</strong> Progressive weekly mileage targets from your training plan.<br/>
                <br/>
                • <strong>Green distance labels</strong> = Goal achieved or exceeded<br/>
                • <strong>Gray distance labels</strong> = Goal not met<br/>
                • <strong>Dashed line</strong> = Your target for that week<br/>
                <br/>
                <em>Goals progress based on your training phase (base building, peak, taper, etc.)</em>
              </div>
            </div>
            <div className="flex items-center gap-2 relative group">
              <div className="w-4 h-4 bg-red-500 rounded"></div>
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
