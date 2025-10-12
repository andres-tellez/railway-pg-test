import React, { useState } from "react";

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

interface LongestRunsChartProps {
  data: LongestRunData[];
  title?: string;
  showHeader?: boolean;
}

export default function LongestRunsChart({ data, title = "Weekly Longest Runs", showHeader = true }: LongestRunsChartProps) {
  const [hoveredRun, setHoveredRun] = useState<{ index: number; x: number; y: number } | null>(null);

  // Find max distance for scaling
  const maxDistance = Math.max(...data.map((run) => run.distance), 1);

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

  const getRunColor = (run: LongestRunData) => {
    if (run.is_personal_record) return "bg-green-500";
    if (run.is_significant_drop) return "bg-red-500";
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
          <div className="flex items-end space-x-1 h-48 bg-gradient-to-t from-gray-100 to-gray-50 p-6 rounded-xl">
            {data.map((run, index) => {
              const heightPixels = calculateHeight(run.distance);

              return (
              <div
                key={run.activity_id}
                className="flex flex-col items-center justify-end flex-1 min-w-0 group relative"
              >
                {/* Bar */}
                <div
                  className={`w-full ${getRunColor(run)} rounded-t-lg transition-all duration-75 cursor-pointer relative hover:scale-105 hover:shadow-lg`}
                  style={{
                    height: `${heightPixels}px`,
                    transition: 'all 0.075s cubic-bezier(0.4, 0, 0.2, 1)'
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
                <div className="w-4 h-4 bg-green-500 rounded"></div>
                <span>Personal Record</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-500 rounded"></div>
                <span>Normal</span>
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
