import React, { useEffect, useState } from "react";
import { useApiClient } from "../utils/apiClient";
import { LongestRunsResponse, LongestRunData, LongestRunsConfig } from "../schemas/longestRuns";

export default function LongestRuns() {
  const api = useApiClient();
  const [runsData, setRunsData] = useState<LongestRunsResponse | null>(null);
  const [config, setConfig] = useState<LongestRunsConfig | null>(null);
  const [selectedWeeks, setSelectedWeeks] = useState<number>(8);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredRun, setHoveredRun] = useState<{ index: number; x: number; y: number } | null>(null);

  // Fetch configuration
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await api.get<LongestRunsConfig>("/api/longest-runs/config");
        setConfig(response.data);
        setSelectedWeeks(response.data.time_periods.default);
      } catch (err) {
        console.error("Failed to fetch config:", err);
      }
    };
    fetchConfig();
  }, []);

  // Fetch longest runs data
  useEffect(() => {
    const fetchLongestRuns = async () => {
      if (!config) return;

      try {
        setLoading(true);
        console.log(`📊 Fetching longest runs for ${selectedWeeks} weeks...`);
        const startTime = performance.now();

        const response = await api.get<LongestRunsResponse>(
          `/api/longest-runs/data?weeks=${selectedWeeks}`
        );

        const loadTime = performance.now() - startTime;
        console.log(`📊 Longest runs loaded in ${loadTime.toFixed(0)}ms`);
        console.log("📊 Response:", response.data);

        setRunsData(response.data);
        setError(null);
      } catch (err) {
        console.error("Failed to fetch longest runs:", err);
        setError("Failed to load longest runs. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchLongestRuns();
  }, [selectedWeeks, config]);

  // Get color for run bar based on flags
  const getRunColor = (run: LongestRunData): string => {
    if (run.is_personal_record) return "bg-green-500 hover:bg-green-600";
    if (run.is_significant_drop) return "bg-red-500 hover:bg-red-600";
    return "bg-blue-500 hover:bg-blue-600";
  };


  // Format date to display format
  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  // Format week label
  const formatWeekLabel = (weekStart: string, index: number): string => {
    return `Week ${index + 1}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6 flex items-center justify-center">
        <div className="text-white text-xl">Loading longest runs...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
        <div className="bg-red-500/10 border border-red-500 rounded-lg p-4 text-red-500">
          {error}
        </div>
      </div>
    );
  }

  if (!runsData || !config) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
        <div className="text-white text-xl">No data available</div>
      </div>
    );
  }

  // Calculate max distance for scaling bars
  const maxDistance = Math.max(...runsData.runs.map((r) => r.distance), 1);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Longest Run Comparison</h1>
            <p className="text-gray-400">Track your weekly longest runs and progress over time</p>
          </div>

          {/* Time Period Selector */}
          <div className="flex gap-2">
            {config.time_periods.options.map((weeks) => (
              <button
                key={weeks}
                onClick={() => setSelectedWeeks(weeks)}
                className={`px-4 py-2 rounded-lg font-medium transition-all ${
                  selectedWeeks === weeks
                    ? "bg-blue-500 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {weeks}w
              </button>
            ))}
          </div>
        </div>


        {/* Chart */}
        <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold text-white mb-6">Weekly Longest Runs</h2>

          {runsData.runs.length === 0 ? (
            <div className="text-center text-gray-400 py-12">
              No runs found for the selected time period
            </div>
          ) : (
            <div className="space-y-4">
              {/* Legend */}
              <div className="flex gap-6 text-sm text-gray-400 mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-green-500 rounded"></div>
                  <span>Personal Record</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-blue-500 rounded"></div>
                  <span>Normal</span>
                </div>
                <div className="flex items-center gap-2 relative group">
                  <div className="w-4 h-4 bg-red-500 rounded"></div>
                  <span>Significant Drop</span>
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-72 bg-gray-900 border border-gray-600 rounded-lg p-3 text-xs text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                    <strong>Significant Drop:</strong> Red bars indicate concerning patterns:<br/>
                    • Two consecutive weeks dropping &gt;20% and &gt;10%<br/>
                    • Single week dropping &gt;30%<br/>
                    <br/>
                    <em>Note: Intentional recovery/taper weeks are filtered out</em>
                  </div>
                </div>
              </div>

              {/* Bar Chart */}
              <div className="grid grid-cols-4 md:grid-cols-8 gap-4">
                {runsData.runs.map((run, index) => (
                  <div
                    key={run.activity_id}
                    className="flex flex-col items-center relative"
                    onMouseEnter={(e) => {
                      const rect = e.currentTarget.getBoundingClientRect();
                      setHoveredRun({
                        index,
                        x: rect.left + rect.width / 2,
                        y: rect.top,
                      });
                    }}
                    onMouseLeave={() => setHoveredRun(null)}
                  >
                    {/* Bar */}
                    <div className="w-full flex flex-col items-center justify-end h-64">
                      <div
                        className={`w-full ${getRunColor(run)} rounded-t-lg transition-all cursor-pointer relative group`}
                        style={{
                          height: `${(run.distance / maxDistance) * 100}%`,
                          minHeight: "20px",
                        }}
                      >
                        {/* Distance Label */}
                        <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-white text-sm font-semibold whitespace-nowrap">
                          {run.distance.toFixed(1)}
                        </div>
                      </div>
                    </div>

                    {/* Labels */}
                    <div className="mt-2 text-center">
                      <div className="text-xs text-gray-500">
                        {formatDate(run.date)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Tooltip */}
              {hoveredRun !== null && (
                <div
                  className="fixed z-50 bg-gray-900 border border-gray-700 rounded-lg p-4 shadow-xl pointer-events-none"
                  style={{
                    left: `${hoveredRun.x}px`,
                    top: `${hoveredRun.y - 10}px`,
                    transform: "translate(-50%, -100%)",
                    minWidth: "250px",
                  }}
                >
                  {(() => {
                    const run = runsData.runs[hoveredRun.index];
                    return (
                      <>
                        <div className="text-white font-semibold mb-2">{run.name}</div>
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-400">Distance:</span>
                            <span className="text-white font-medium">{run.distance.toFixed(2)} mi</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Pace:</span>
                            <span className="text-white font-medium">{run.pace} min/mi</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Duration:</span>
                            <span className="text-white font-medium">{run.duration}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Date:</span>
                            <span className="text-white font-medium">{formatDate(run.date)}</span>
                          </div>
                          {run.prev_week_distance && (
                            <div className="flex justify-between">
                              <span className="text-gray-400">vs Last Week:</span>
                              <span className={`font-medium ${run.change_pct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                {run.change_pct >= 0 ? '+' : ''}{run.change_pct.toFixed(1)}%
                              </span>
                            </div>
                          )}
                          {run.is_personal_record && (
                            <div className="mt-2 pt-2 border-t border-gray-700 text-green-500 font-semibold text-center">
                              🎉 Personal Record!
                            </div>
                          )}
                          {run.is_significant_drop && (
                            <div className="mt-2 pt-2 border-t border-gray-700 text-red-500 font-semibold text-center">
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
          )}
        </div>

      </div>
    </div>
  );
}
