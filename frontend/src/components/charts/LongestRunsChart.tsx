import React, { useState, useMemo } from "react";

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

interface WeeklyGoalData {
  week: string;
  goal_miles: number;
}

interface LongestRunsChartProps {
  data: LongestRunData[];
  title?: string;
  showHeader?: boolean;
  weeklyGoals?: WeeklyGoalData[]; // Same pattern as WeeklyTrendChart
}

export default function LongestRunsChart({ data, weeklyGoals = [], title = "Weekly Longest Runs", showHeader = true }: LongestRunsChartProps) {
  const [hoveredRun, setHoveredRun] = useState<{ index: number; x: number; y: number } | null>(null);

  // Helper function to find goal for a specific week (same pattern as WeeklyTrendChart)
  const findGoalForWeek = (week: string): number | null => {
    console.log(`[LongestRuns] Looking for goal for week: ${week}`);
    console.log(`[LongestRuns] Available goals:`, weeklyGoals.map(g => ({ week: g.week, goal_miles: g.goal_miles })));

    // Extract just the date part (YYYY-MM-DD) from the week string
    const dateOnly = week.split('T')[0];

    // Try exact match first - compare both full week string and date-only
    let goal = weeklyGoals.find(g => g.week === week || g.week === dateOnly || g.week.split('T')[0] === dateOnly);

    if (goal) {
      console.log(`[LongestRuns] Found exact match: ${goal.goal_miles} miles for ${week}`);
      return goal.goal_miles;
    }

    // If no exact match, try to find the closest week using date comparison
    const runDate = new Date(week);
    let closestGoal = null;
    let smallestDiff = Infinity;

    for (const g of weeklyGoals) {
      const goalDate = new Date(g.week);
      const diff = Math.abs(runDate.getTime() - goalDate.getTime());

      if (diff < smallestDiff) {
        smallestDiff = diff;
        closestGoal = g;
      }
    }

    // Only return if the closest goal is within 1 day (much stricter)
    const result = closestGoal && smallestDiff <= 1 * 24 * 60 * 60 * 1000 ? closestGoal.goal_miles : null;
    console.log(`[LongestRuns] Closest goal result: ${result} miles (diff: ${smallestDiff / (24 * 60 * 60 * 1000)} days)`);
    return result;
  };

  // Optimized chart data calculation (same pattern as WeeklyTrendChart)
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    const maxDistance = Math.max(...data.map((run) => run.distance), 1);

    // Calculate bar colors based on data
    const barColors = data.map((run) => {
      if (run.is_personal_record) return 'personal_record';
      if (run.is_significant_drop) return 'significant_drop';
      return 'normal';
    });

    return { maxDistance, barColors };
  }, [data]);

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

  const { maxDistance, barColors } = chartData;

  // Calculate height in pixels (same as WeeklyTrendChart)
  const calculateHeight = (distance: number) => {
    const heightPercentage = maxDistance > 0 ? (distance / maxDistance) : 0;
    return heightPercentage * 140;
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

  const getRunColor = (colorType: string) => {
    if (colorType === 'personal_record') return "bg-green-500";
    if (colorType === 'significant_drop') return "bg-red-500";
    return "bg-blue-500";
  };

  const getTrendIcon = (trend: string) => {
    if (trend === 'improving') return '↑';
    if (trend === 'declining') return '↓';
    return '→';
  };

  const formatHeartRateZones = (zones: any) => {
    if (!zones) return null;
    return (
      <div className="space-y-1">
        {zones.zone_1 > 0 && <div className="flex justify-between"><span>Zone 1:</span><span>{zones.zone_1}%</span></div>}
        {zones.zone_2 > 0 && <div className="flex justify-between"><span>Zone 2:</span><span>{zones.zone_2}%</span></div>}
        {zones.zone_3 > 0 && <div className="flex justify-between"><span>Zone 3:</span><span>{zones.zone_3}%</span></div>}
        {zones.zone_4 > 0 && <div className="flex justify-between"><span>Zone 4:</span><span>{zones.zone_4}%</span></div>}
        {zones.zone_5 > 0 && <div className="flex justify-between"><span>Zone 5:</span><span>{zones.zone_5}%</span></div>}
      </div>
    );
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
      {showHeader && (
        <div className="mb-6">
          <h3 className="text-xl font-bold text-gray-900">{title}</h3>
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
            // Calculate the actual tallest bar height in pixels
            const tallestBarHeight = data.reduce((max, run) => {
              const heightPixels = calculateHeight(run.distance);
              return Math.max(max, heightPixels);
            }, 0);

            // Add more padding above the tallest bar so numbers appear well within background
            const totalHeight = tallestBarHeight + 80;

            return (
              <div
                style={{
                  height: `${totalHeight}px`,
                  display: 'flex',
                  alignItems: 'flex-end',
                  gap: '0.25rem',
                  padding: '1.5rem',
                  borderRadius: '0.75rem',
                  background: 'linear-gradient(to top, rgb(243 244 246), rgb(249 250 251))'
                }}
              >
                {data.map((run, index) => {
                  const heightPixels = calculateHeight(run.distance);
              const goalMiles = findGoalForWeek(run.week_start);
              const goalHeightPixels = goalMiles ? (goalMiles / run.distance) * heightPixels : 0;
              const exceededGoal = goalMiles ? run.distance >= goalMiles : false;
              const barColor = barColors[index];

              return (
              <div
                key={run.activity_id}
                style={{
                  flex: '1 1 0',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  minWidth: 0
                }}
              >
                {/* Bar */}
                <div
                  className={`${getRunColor(barColor)}`}
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
                    setHoveredRun({
                      index,
                      x: rect.left + rect.width / 2,
                      y: rect.top - 10,
                    });
                  }}
                  onMouseLeave={() => setHoveredRun(null)}
                >
                  {/* Distance Label */}
                  <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-gray-700 text-sm font-semibold whitespace-nowrap">
                    {run.distance.toFixed(1)}
                  </div>

                  {/* OPTION 2: Subtle Goal Zone with Better Visual Hierarchy (same as WeeklyTrendChart) */}
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

                  {/* Goal Label */}
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

                {/* Labels */}
                <div className="mt-2 text-center">
                  <div className="text-xs text-gray-500">
                    {formatDate(run.date)}
                  </div>
                </div>
              </div>
              );
            })}
              </div>
            );
          })()}

          {/* Hover Tooltip */}
          {hoveredRun !== null && (
            <div
              className="fixed z-50 bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-600 rounded-lg p-3 shadow-2xl pointer-events-none backdrop-blur-sm"
              style={{
                left: `${hoveredRun.x}px`,
                top: `${hoveredRun.y}px`,
                transform: "translate(-50%, -100%)",
                minWidth: "180px",
                backdropFilter: 'blur(8px)',
              }}
            >
              {(() => {
                const run = data[hoveredRun.index];
                return (
                  <>
                    {/* Date Header */}
                    <div className="text-sm font-bold text-blue-400 mb-2 pb-2 border-b border-gray-600">
                      Wk of {formatDate(run.week_start)}
                    </div>

                    {/* Run Name */}
                    <div className="text-white font-semibold mb-2 text-sm">
                      {run.name}
                    </div>

                    {/* Stats */}
                    <div className="space-y-1 text-xs text-gray-300">
                      <div className="flex items-center gap-1">
                        <span className="text-gray-400">Distance:</span>
                        <span className="text-white font-semibold">{run.distance.toFixed(2)} mi</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-gray-400">Pace:</span>
                        <span className="text-white font-semibold">{run.pace}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-gray-400">Duration:</span>
                        <span className="text-white font-semibold">{run.duration}</span>
                      </div>

                      {/* Trend Info */}
                      {run.prev_week_distance && (
                        <div className="flex items-center gap-1 pt-1 border-t border-gray-700">
                          <span className="text-gray-400">vs Last Week:</span>
                          <span className={`font-semibold ${run.change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {getTrendIcon(run.trend)} {run.change_pct >= 0 ? '+' : ''}{run.change_pct.toFixed(1)}%
                          </span>
                        </div>
                      )}

                      {/* Special Badges */}
                      {run.is_personal_record && (
                        <div className="pt-1 border-t border-gray-700">
                          <span className="text-green-400 font-semibold">🏆 Personal Record!</span>
                        </div>
                      )}
                      {run.is_significant_drop && (
                        <div className="pt-1 border-t border-gray-700">
                          <span className="text-red-400 font-semibold">⚠️ Significant Drop</span>
                        </div>
                      )}

                      {/* Heart Rate Zones */}
                      {run.heart_rate_zones && (
                        <div className="pt-2 border-t border-gray-700">
                          <div className="text-gray-400 mb-1">HR Zones:</div>
                          {formatHeartRateZones(run.heart_rate_zones)}
                        </div>
                      )}
                    </div>
                  </>
                );
              })()}
            </div>
          )}

          {/* Legend positioned below bars on the right */}
          <div className="flex justify-end mt-4">
            <div className="flex gap-6 text-sm text-gray-600">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-500 rounded"></div>
                <span>Actual</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-600 rounded border-2 border-black"></div>
                <span>Plan</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-green-500 rounded"></div>
                <span>Personal Record</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-red-500 rounded"></div>
                <span>Significant Drop</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
