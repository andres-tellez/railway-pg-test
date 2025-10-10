import React, { useEffect, useState } from "react";
import { useApiClient } from "../utils/apiClient";
import WeeklyVO2Chart from "../components/charts/WeeklyVO2Chart";

interface WeeklyVO2Data {
  week: string;
  vo2_estimate: number | null;
  run_score: number | null;
}

export default function VO2Metrics() {
  const api = useApiClient();
  const [weeklyVO2, setWeeklyVO2] = useState<WeeklyVO2Data[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVO2Data = async () => {
      try {
        console.log("💪 Fetching VO2 Max data...");
        const startTime = performance.now();

        // Fetch all metrics (includes VO2 data)
        const response = await api.get<{
          weekly_vo2_estimates: WeeklyVO2Data[];
        }>("/api/metrics/all-metrics");

        const loadTime = performance.now() - startTime;
        console.log(`💪 VO2 data loaded in ${loadTime.toFixed(0)}ms`);
        console.log("💪 VO2 response:", response.data);

        const data = response.data;

        // Extract VO2 estimates
        if (data.weekly_vo2_estimates && data.weekly_vo2_estimates.length > 0) {
          setWeeklyVO2(data.weekly_vo2_estimates);
          console.log(`💪 Found ${data.weekly_vo2_estimates.length} weeks of VO2 data`);
        } else {
          console.warn("💪 No VO2 data found in response");
          setWeeklyVO2([]);
        }

        setError(null);
      } catch (err: any) {
        console.error("Error fetching VO2 data:", err);
        setError(err.response?.data?.error || "Failed to load VO2 data. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchVO2Data();
  }, [api]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-purple-600 mx-auto mb-4"></div>
          <p className="text-xl font-semibold text-gray-700">Loading VO2 Max data...</p>
          <p className="text-sm text-gray-500 mt-2">Analyzing your fitness metrics</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full border border-red-200">
          <div className="text-center">
            <div className="text-6xl mb-4">⚠️</div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Unable to Load Data</h2>
            <p className="text-gray-600 mb-6">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const helpContent = {
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
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            VO2 Max Tracking
          </h1>
          <p className="text-gray-600 text-lg">
            Monitor your cardiovascular fitness over time
          </p>
        </div>

        {/* VO2 Chart */}
        <div className="mb-6">
          <WeeklyVO2Chart
            data={weeklyVO2}
            title="Weekly VO2 Max Estimate"
            showHeader={true}
            helpTooltip={helpContent}
          />
        </div>

        {/* Info Card */}
        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
          <h3 className="text-lg font-bold text-gray-900 mb-4">About VO2 Max</h3>
          <div className="space-y-3 text-gray-600">
            <p>
              <strong className="text-gray-900">What is VO2 Max?</strong> It's the maximum amount of oxygen your body can use during intense exercise. Higher values indicate better cardiovascular fitness.
            </p>
            <p>
              <strong className="text-gray-900">How is it calculated?</strong> Our algorithm estimates VO2 Max based on your running performance, including distance, time, and heart rate data.
            </p>
            <p>
              <strong className="text-gray-900">What's a good VO2 Max?</strong> This varies by age and gender, but generally:
            </p>
            <ul className="list-disc list-inside ml-4 space-y-1">
              <li>Excellent: 50+ (male), 45+ (female)</li>
              <li>Good: 40-50 (male), 35-45 (female)</li>
              <li>Average: 35-40 (male), 30-35 (female)</li>
            </ul>
            <p className="mt-4 text-sm text-purple-600 font-medium">
              💡 Focus on improving your own baseline rather than comparing to others!
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
