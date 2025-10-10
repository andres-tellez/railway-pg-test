import React, { useMemo, useState } from 'react';
import ChartHelpTooltip from './ChartHelpTooltip';

interface WeeklyDistanceData {
  week: string;
  distance: number;
  runs: number;
  avgPace: string;
}

interface WeeklyDistanceChartProps {
  data: WeeklyDistanceData[];
  title?: string;
  totalMiles?: number;
  avgWeeklyMiles?: number;
}

export default function WeeklyDistanceChart({
  data,
  title = "Mileage",
  totalMiles,
  avgWeeklyMiles
}: WeeklyDistanceChartProps) {
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
        <h3 className="text-xl font-bold text-gray-900 mb-4">{title}</h3>
        <div className="text-center py-12 text-gray-400">
          <div className="text-5xl mb-4 opacity-50">📈</div>
          <p className="text-lg font-medium">No distance data available</p>
          <p className="text-sm mt-2">Complete a few weeks of training to see trends</p>
        </div>
      </div>
    );
  }

  const { maxDistance } = chartData;

  const helpContent = {
    title: "Weekly Mileage",
    quickTip: "Think of weekly miles as your fitness savings account - more deposits = stronger endurance!",
    detailedExplanation: {
      why: "Consistent weekly volume builds your aerobic engine and prevents injuries through gradual strengthening.",
      benefits: [
        "Builds your aerobic base",
        "Prevents injuries through gradual adaptation",
        "Strongest predictor of race performance"
      ],
      tips: [
        "Increase by 10% max per week",
        "80% easy pace, 20% hard",
        "Longest run = 20-30% of weekly total"
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
        <div className="flex items-center space-x-4 text-sm text-gray-600">
          {totalMiles && (
            <span>Total: <span className="font-semibold text-blue-600">{Math.round(totalMiles)} mi</span></span>
          )}
          {avgWeeklyMiles && (
            <span>Avg: <span className="font-semibold text-blue-600">{Math.round(avgWeeklyMiles)} mi</span></span>
          )}
        </div>
      </div>

      <div className="relative">
        <div className="flex items-end space-x-1 h-48 bg-gradient-to-t from-gray-50 to-white p-6 rounded-xl border border-gray-100">
          {data.map((week, index) => {
            const heightPercentage = maxDistance > 0 ? (week.distance / maxDistance) : 0;
            const heightPixels = Math.max(heightPercentage * 120 + 40, 40);
            const isCurrentWeek = index === 0;

            return (
              <div key={index} className="flex flex-col items-center justify-end flex-1 min-w-0 group">
                {isCurrentWeek && (
                  <div className="text-sm font-bold text-gray-800 mb-2">
                    {week.distance.toFixed(1)}
                  </div>
                )}
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
                {new Date(data[hoveredBar.index].week + 'T00:00:00').toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric'
                })}
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
  );
}
