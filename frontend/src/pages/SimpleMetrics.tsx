import React, { useEffect, useState } from "react";
import { useApiClient } from "../utils/apiClient";
import HeartRateZoneChart from "../components/charts/HeartRateZoneChart";
import WeeklyTrendChart from "../components/charts/WeeklyTrendChart";

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

export default function SimpleMetrics() {
  const api = useApiClient();
  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [hrZones, setHrZones] = useState<any>(null);
  const [weeklyTrends, setWeeklyTrends] = useState<WeeklyTrendData[]>([]);
  const [weeklyHRZones, setWeeklyHRZones] = useState<WeeklyHRZoneData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        console.log("📊 Fetching ALL metrics in single call...");
        const startTime = performance.now();

        // Single API call for everything
        const response = await api.get<DashboardMetrics & {weekly_trends: WeeklyTrendData[], weekly_hr_zones: WeeklyHRZoneData[]}>("/api/metrics/all-metrics");

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
        setWeeklyTrends(data.weekly_trends);
        setWeeklyHRZones(data.weekly_hr_zones);

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
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">
            Training Metrics
          </h1>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="bg-white rounded-lg shadow-md p-6 border border-gray-200 animate-pulse"
              >
                <div className="h-4 bg-gray-200 rounded w-24 mb-4"></div>
                <div className="h-12 bg-gray-200 rounded w-32 mb-4"></div>
                <div className="h-4 bg-gray-200 rounded w-28"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Training Metrics
          </h1>
          {error && (
            <div className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-md">
              {error}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {metrics.map((metric, index) => (
            <div
              key={index}
              className="bg-white rounded-lg shadow-md p-6 border border-gray-200 hover:shadow-lg transition-shadow"
            >
              <p className="text-sm text-gray-600 mb-2">{metric.title}</p>
              <div className="flex items-baseline gap-2 mb-4">
                <span className="text-4xl font-bold text-gray-900">
                  {metric.value}
                </span>
                <span className="text-sm text-gray-500">{metric.unit}</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`text-sm font-medium ${
                    metric.isPositive ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {metric.change}
                </span>
                <span className="text-sm text-gray-500">vs last week</span>
              </div>
            </div>
          ))}
        </div>

        {/* Charts Section */}
        <div className="mt-8 space-y-6">
          {/* Weekly Trend Chart - Full Width */}
          {weeklyTrends.length > 0 && (
            <WeeklyTrendChart
              data={weeklyTrends}
              title="Weekly Running Trends"
              totalMiles={weeklyTrends.reduce((sum, week) => sum + week.distance, 0)}
              avgWeeklyMiles={weeklyTrends.reduce((sum, week) => sum + week.distance, 0) / weeklyTrends.length}
              hrZoneData={weeklyHRZones}
            />
          )}

        </div>

      </div>
    </div>
  );
}
