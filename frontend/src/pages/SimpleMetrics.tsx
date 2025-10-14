import React, { useEffect, useState } from "react";
import { useApiClient } from "../utils/apiClient";
import HeartRateZoneChart from "../components/charts/HeartRateZoneChart";
import TotalMilesActualVsPlanChart from "../components/charts/TotalMilesActualVsPlanChart";
import WeeklyPaceChart from "../components/charts/WeeklyPaceChart";
import WeeklyVO2Chart from "../components/charts/WeeklyVO2Chart";
import LongestRunsChart from "../components/charts/LongestRunsChart";
import ChartHelpTooltip from "../components/charts/ChartHelpTooltip";

interface MetricData {
  title: string;
  value: string;
  unit: string;
  change: string;
  isPositive: boolean;
}

interface DashboardMetrics {
  weekly_distance: {
    current: number;
    previous: number;
    change_pct: number;
  };
  average_pace: {
    current: string;
    previous: string;
    change_pct: number;
  };
  weekly_runs: {
    current: number;
    previous: number;
    change_pct: number;
  };
  hr_zones: {
    zone_1: number;
    zone_2: number;
    zone_3: number;
    zone_4: number;
    zone_5: number;
  };
}

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

interface WeeklyVO2Data {
  week: string;
  vo2_estimate: number | null;
  run_score: number | null;
}

interface WeeklyGoalData {
  week: string;
  goal_miles: number;
}

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

export default function SimpleMetrics() {
  const api = useApiClient();
  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [hrZones, setHrZones] = useState<any>(null);
  const [weeklyTrends, setWeeklyTrends] = useState<WeeklyTrendData[]>([]);
  const [weeklyHRZones, setWeeklyHRZones] = useState<WeeklyHRZoneData[]>([]);
  const [weeklyVO2, setWeeklyVO2] = useState<WeeklyVO2Data[]>([]);
  const [weeklyGoals, setWeeklyGoals] = useState<WeeklyGoalData[]>([]);
  const [longestRuns, setLongestRuns] = useState<LongestRunData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredHRBar, setHoveredHRBar] = useState<{ index: number; x: number; y: number } | null>(null);
  // Set default based on screen size - 8 for desktop, 4 for mobile
  const [selectedWeeks, setSelectedWeeks] = useState<number>(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth >= 768 ? 8 : 4;
    }
    return 8; // fallback for SSR
  });
  const [allWeeklyData, setAllWeeklyData] = useState<{
    trends: WeeklyTrendData[];
    hrZones: WeeklyHRZoneData[];
    vo2: WeeklyVO2Data[];
    goals: WeeklyGoalData[];
    longestRuns: LongestRunData[];
  }>({ trends: [], hrZones: [], vo2: [], goals: [], longestRuns: [] });

  // Handle window resize to update default weeks
  useEffect(() => {
    const handleResize = () => {
      if (typeof window !== 'undefined') {
        const isMobile = window.innerWidth < 768;
        const newDefault = isMobile ? 4 : 8;
        // Only update if current selection is the old default
        if (selectedWeeks === (isMobile ? 8 : 4)) {
          setSelectedWeeks(newDefault);
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [selectedWeeks]);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        console.log("📊 Fetching ALL metrics in single call...");
        const startTime = performance.now();

        // Single API call for everything (always fetch all 20 weeks)
        const response = await api.get<DashboardMetrics & {weekly_trends: WeeklyTrendData[], weekly_hr_zones: WeeklyHRZoneData[], weekly_vo2_estimates: WeeklyVO2Data[], weekly_goals: WeeklyGoalData[], longest_runs: LongestRunData[]}>("/api/metrics/all-metrics");

        const loadTime = performance.now() - startTime;
        console.log(`📊 All metrics loaded in ${loadTime.toFixed(0)}ms`);
        console.log("📊 Complete response:", response.data);

        const data = response.data;

        // Transform API data to display format
        const displayMetrics: MetricData[] = [
          {
            title: "Weekly Distance",
            value: data.weekly_distance.current.toString(),
            unit: "miles",
            change: `${data.weekly_distance.change_pct >= 0 ? "+" : ""}${data.weekly_distance.change_pct.toFixed(1)}%`,
            isPositive: data.weekly_distance.change_pct >= 0,
          },
          {
            title: "Average Pace",
            value: data.average_pace.current,
            unit: "min/mi",
            change: `${data.average_pace.change_pct >= 0 ? "+" : ""}${data.average_pace.change_pct.toFixed(1)}%`,
            isPositive: data.average_pace.change_pct >= 0, // For pace, positive change = faster
          },
          {
            title: "Runs This Week",
            value: data.weekly_runs.current.toString(),
            unit: "activities",
            change: `${data.weekly_runs.change_pct >= 0 ? "+" : ""}${data.weekly_runs.change_pct.toFixed(1)}%`,
            isPositive: data.weekly_runs.change_pct >= 0,
          },
        ];

        setMetrics(displayMetrics);
        setHrZones(data.hr_zones);

        // Store all data for filtering
        setAllWeeklyData({
          trends: data.weekly_trends,
          hrZones: data.weekly_hr_zones,
          vo2: data.weekly_vo2_estimates || [],
          goals: data.weekly_goals || [],
          longestRuns: data.longest_runs || []
        });

      } catch (err) {
        console.error("Failed to fetch metrics:", err);
        setError("Failed to load metrics. Please try again.");

        // Fallback to placeholder data on error
        setMetrics([
          {
            title: "Weekly Distance",
            value: "0",
            unit: "miles",
            change: "0%",
            isPositive: true,
          },
          {
            title: "Average Pace",
            value: "0:00",
            unit: "min/mi",
            change: "0%",
            isPositive: true,
          },
          {
            title: "Runs This Week",
            value: "0",
            unit: "activities",
            change: "0%",
            isPositive: true,
          },
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, []); // Remove selectedWeeks dependency - only fetch once

  // Compute filtered data based on selected weeks (instant filtering)
  const filteredWeeklyTrends = allWeeklyData.trends.slice(0, selectedWeeks);
  const filteredWeeklyHRZones = allWeeklyData.hrZones.slice(0, selectedWeeks);
  const filteredWeeklyVO2 = allWeeklyData.vo2.slice(0, selectedWeeks);
  const filteredWeeklyGoals = allWeeklyData.goals.slice(0, selectedWeeks);
  const filteredLongestRuns = allWeeklyData.longestRuns.slice(0, selectedWeeks);

  // Debug logging
  console.log(`📊 Data availability: ${allWeeklyData.trends.length} trends, ${allWeeklyData.hrZones.length} HR zones, ${allWeeklyData.vo2.length} VO2`);
  console.log(`📊 Selected weeks: ${selectedWeeks}, Filtered: ${filteredWeeklyTrends.length} trends, ${filteredWeeklyHRZones.length} HR zones, ${filteredWeeklyVO2.length} VO2`);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          {/* Unified Weekly Trends Card Loading */}
          <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100 animate-pulse">
            <div className="h-8 bg-gray-200 rounded w-48 mb-6"></div>
            <div className="space-y-8">
              <div>
                <div className="h-6 bg-gray-200 rounded w-32 mb-4"></div>
                <div className="h-48 bg-gray-200 rounded"></div>
              </div>
              <div>
                <div className="h-6 bg-gray-200 rounded w-40 mb-4"></div>
                <div className="h-48 bg-gray-200 rounded"></div>
              </div>
              <div>
                <div className="h-6 bg-gray-200 rounded w-24 mb-4"></div>
                <div className="h-48 bg-gray-200 rounded"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Help content for each section
  const mileageHelpContent = {
    title: "Weekly Mileage",
    quickTip: "Think of mileage like a fitness savings account - every mile builds your endurance foundation!",
    detailedExplanation: {
      why: "Consistent weekly volume is the foundation of endurance training. It builds aerobic capacity and injury resistance.",
      benefits: [
        "Builds aerobic base and endurance",
        "Improves running economy and efficiency",
        "Reduces injury risk through gradual adaptation"
      ],
      tips: [
        "Increase weekly mileage by 10-15% maximum",
        "Include one longer run each week",
        "Take recovery weeks every 3-4 weeks"
      ]
    }
  };

  const hrZoneHelpContent = {
    title: "Heart Rate Zones",
    quickTip: "HR zones are like gears in a car - each zone serves a different training purpose.",
    detailedExplanation: {
      why: "Different heart rate zones target different energy systems and adaptations for comprehensive fitness development.",
      benefits: [
        "Targets specific energy systems effectively",
        "Prevents overtraining and burnout",
        "Ensures balanced fitness development"
      ],
      tips: [
        "Spend 80% of time in easy zones (1-2)",
        "Use zones 4-5 for high-intensity sessions",
        "Monitor zone distribution weekly"
      ]
    }
  };

  const paceHelpContent = {
    title: "Pace Trends",
    quickTip: "Getting faster at the same effort level shows your fitness is improving!",
    detailedExplanation: {
      why: "Pace progression indicates fitness gains. As you get stronger, you can run faster with the same effort.",
      benefits: [
        "Shows fitness improvements objectively",
        "Helps set realistic race goals",
        "Guides workout pace selection"
      ],
      tips: [
        "Focus on easy run pace improvements first",
        "Track trends over 4-6 weeks",
        "Don't chase pace every run - effort matters more"
      ]
    }
  };

  const vo2HelpContent = {
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
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {error && (
          <div className="mb-6">
            <div className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-md">
              {error}
            </div>
          </div>
        )}

        {/* Weekly Trends Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Weekly Trends</h1>
            <p className="text-gray-400">Track your training progress over time</p>
          </div>

          {/* Time Period Selector */}
          <div className="flex gap-2">
            {[4, 8, 16].map((weeks) => (
              <button
                key={weeks}
                onClick={() => setSelectedWeeks(weeks)}
                className={`px-4 py-2 rounded-lg font-medium transition-all ${
                  selectedWeeks === weeks
                    ? "bg-gray-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {weeks}w
              </button>
            ))}
          </div>
        </div>

        {/* Charts without outer card */}
        <div className="space-y-12">

          {/* Mileage Section */}
          {filteredWeeklyTrends.length > 0 && (
            <TotalMilesActualVsPlanChart
              data={filteredWeeklyTrends}
              weeklyGoals={filteredWeeklyGoals}
              title="Total Miles - Actual vs Plan"
              showHeader={true}
              helpTooltip={mileageHelpContent}
            />
          )}

          {/* Longest Runs Section */}
          {filteredLongestRuns.length > 0 && (
            <LongestRunsChart
              data={filteredLongestRuns}
              weeklyGoals={filteredWeeklyGoals}
              title="Longest Runs"
              showHeader={true}
            />
          )}

          {/* HR Zones Section */}
          {filteredWeeklyHRZones.length > 0 && (
            <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
              <div className="flex items-center gap-3 mb-6">
                <h3 className="text-xl font-bold text-gray-900">HR Zones</h3>
                <ChartHelpTooltip helpContent={hrZoneHelpContent} />
              </div>

              {/* HR Zone Chart */}
              <div className="relative">
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
                    // Calculate the actual tallest bar height in pixels
                    const tallestBarHeight = filteredWeeklyHRZones.reduce((max, week) => {
                      const totalZones = week.zone_1 + week.zone_2 + week.zone_3 + week.zone_4 + week.zone_5;
                      const maxTotal = Math.max(...filteredWeeklyHRZones.map(w => w.zone_1 + w.zone_2 + w.zone_3 + w.zone_4 + w.zone_5));
                      const heightPercentage = maxTotal > 0 ? (totalZones / maxTotal) : 0;
                      const heightPixels = Math.max(heightPercentage * 120 + 40, 40);
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
                        {filteredWeeklyHRZones.map((week, index) => {
                          const totalZones = week.zone_1 + week.zone_2 + week.zone_3 + week.zone_4 + week.zone_5;
                          const maxTotal = Math.max(...filteredWeeklyHRZones.map(w => w.zone_1 + w.zone_2 + w.zone_3 + w.zone_4 + w.zone_5));
                          const heightPercentage = maxTotal > 0 ? (totalZones / maxTotal) : 0;
                          const heightPixels = Math.max(heightPercentage * 120 + 40, 40);

                      const zoneColors = {
                        zone_1: '#3B82F6', // Blue - Recovery
                        zone_2: '#10B981', // Green - Aerobic Base
                        zone_3: '#F59E0B', // Orange - Tempo
                        zone_4: '#DC2626', // Red - Threshold
                        zone_5: '#8B5CF6'  // Purple - VO2 Max
                      };

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
                              console.log('HR Zone hover:', weeklyHRZones[index]);
                              setHoveredHRBar({
                                index,
                                x: rect.left + rect.width / 2,
                                y: rect.top - 10
                              });
                            }}
                            onMouseLeave={() => setHoveredHRBar(null)}
                          >
                            {/* Stacked zones from bottom to top */}
                            <div
                              className="absolute bottom-0 w-full"
                              style={{
                                height: `${(week.zone_1 / totalZones) * 100}%`,
                                backgroundColor: zoneColors.zone_1,
                                minHeight: week.zone_1 > 0 ? '2px' : '0px'
                              }}
                            />
                            <div
                              className="absolute w-full"
                              style={{
                                bottom: `${(week.zone_1 / totalZones) * 100}%`,
                                height: `${(week.zone_2 / totalZones) * 100}%`,
                                backgroundColor: zoneColors.zone_2,
                                minHeight: week.zone_2 > 0 ? '2px' : '0px'
                              }}
                            />
                            <div
                              className="absolute w-full"
                              style={{
                                bottom: `${((week.zone_1 + week.zone_2) / totalZones) * 100}%`,
                                height: `${(week.zone_3 / totalZones) * 100}%`,
                                backgroundColor: zoneColors.zone_3,
                                minHeight: week.zone_3 > 0 ? '2px' : '0px'
                              }}
                            />
                            <div
                              className="absolute w-full"
                              style={{
                                bottom: `${((week.zone_1 + week.zone_2 + week.zone_3) / totalZones) * 100}%`,
                                height: `${(week.zone_4 / totalZones) * 100}%`,
                                backgroundColor: zoneColors.zone_4,
                                minHeight: week.zone_4 > 0 ? '2px' : '0px'
                              }}
                            />
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

                  {/* HR Zone Tooltip */}
                  {hoveredHRBar && (
                    <div
                      className="fixed z-50 px-2 py-1 bg-gray-800 text-white text-xs rounded shadow-lg pointer-events-none transition-all duration-100 ease-out transform"
                      style={{
                        left: `${hoveredHRBar.x}px`,
                        top: `${hoveredHRBar.y}px`,
                        transform: 'translateX(-50%) translateY(-100%)',
                        opacity: hoveredHRBar ? 1 : 0,
                        animation: 'fadeInUp 0.1s ease-out'
                      }}
                    >
                      <div className="flex flex-col items-center">
                        <div>
                          {(() => {
                            try {
                              const dateStr = filteredWeeklyHRZones[hoveredHRBar.index].week;
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
                              return filteredWeeklyHRZones[hoveredHRBar.index].week;
                            }
                          })()}
                        </div>
                        <div className="text-xs space-y-1 mt-1">
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#3B82F6' }}></div>
                            <span>Z1: {filteredWeeklyHRZones[hoveredHRBar.index].zone_1.toFixed(1)}%</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#10B981' }}></div>
                            <span>Z2: {filteredWeeklyHRZones[hoveredHRBar.index].zone_2.toFixed(1)}%</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#F59E0B' }}></div>
                            <span>Z3: {filteredWeeklyHRZones[hoveredHRBar.index].zone_3.toFixed(1)}%</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#DC2626' }}></div>
                            <span>Z4: {filteredWeeklyHRZones[hoveredHRBar.index].zone_4.toFixed(1)}%</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#8B5CF6' }}></div>
                            <span>Z5: {filteredWeeklyHRZones[hoveredHRBar.index].zone_5.toFixed(1)}%</span>
                          </div>
                        </div>
                      </div>
                      {/* Arrow pointing down */}
                      <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-3 border-r-3 border-t-3 border-transparent border-t-gray-800"></div>
                    </div>
                  )}
                </div>

              </div>
            </div>
          )}

          {/* Pace Section */}
          {filteredWeeklyTrends.length > 0 && (
            <WeeklyPaceChart
              data={filteredWeeklyTrends}
              title="Pace"
              showHeader={true}
              helpTooltip={paceHelpContent}
            />
          )}

          {/* VO2 Max Section */}
          {filteredWeeklyVO2.length > 0 && (
            <WeeklyVO2Chart
              data={filteredWeeklyVO2.map(vo2 => {
                // Find matching weekly trend data to get runs and distance
                const matchingTrend = filteredWeeklyTrends.find(trend => trend.week === vo2.week);
                return {
                  ...vo2,
                  runs: matchingTrend?.runs,
                  distance: matchingTrend?.distance
                };
              })}
              title="VO2 Max Estimate"
              showHeader={true}
              helpTooltip={vo2HelpContent}
            />
          )}
        </div>
      </div>
    </div>
  );
}
