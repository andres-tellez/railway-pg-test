import React from 'react';
import GYRMetricCard from '../components/cards/GYRMetricCard';

export default function GYRMetricsDemo() {
  // Mock data for Weekly Total Runs - Last 8 weeks (most recent first)
  const weeklyTotalRunsScores = [
    { value: 85, date: '2024-06-11', status: 'yellow' as const }, // This week
    { value: 72, date: '2024-06-04', status: 'red' as const },    // 1 week ago
    { value: 0, date: '2024-05-28', status: 'gray' as const },   // 2 weeks ago
    { value: 65, date: '2024-05-21', status: 'red' as const },   // 3 weeks ago
    { value: 88, date: '2024-05-14', status: 'yellow' as const }, // 4 weeks ago
    { value: 93, date: '2024-05-07', status: 'green' as const }, // 5 weeks ago
    { value: 86, date: '2024-04-30', status: 'yellow' as const }, // 6 weeks ago
    { value: 82, date: '2024-04-23', status: 'yellow' as const }  // 7 weeks ago (8 weeks ago)
  ];

  // Mock data for Weekly Pace - Last 8 weeks (most recent first)
  const weeklyPaceScores = [
    { value: 95, date: '2024-06-11', status: 'green' as const }, // This week
    { value: 88, date: '2024-06-04', status: 'yellow' as const }, // 1 week ago
    { value: 92, date: '2024-05-28', status: 'green' as const }, // 2 weeks ago
    { value: 85, date: '2024-05-21', status: 'yellow' as const }, // 3 weeks ago
    { value: 78, date: '2024-05-14', status: 'red' as const },   // 4 weeks ago
    { value: 91, date: '2024-05-07', status: 'green' as const }, // 5 weeks ago
    { value: 87, date: '2024-04-30', status: 'yellow' as const }, // 6 weeks ago
    { value: 83, date: '2024-04-23', status: 'yellow' as const }  // 7 weeks ago
  ];

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">GYR Metrics Demo</h1>
          <p className="text-gray-600">Green/Yellow/Red logic for training metrics</p>
        </div>

        {/* Two Cards Demo */}
        <div className="flex gap-6 justify-center">
          <GYRMetricCard
            title="Total Runs"
            historicalScores={weeklyTotalRunsScores}
            greenCriteria="90–110% of plan"
            yellowCriteria="70–90% or 110–130%"
            redCriteria="<70% or >130%"
          />
          <GYRMetricCard
            title="Weekly Pace"
            historicalScores={weeklyPaceScores}
            greenCriteria="Same or faster"
            yellowCriteria="Up to 10s/mi slower"
            redCriteria=">10s/mi slower"
          />
        </div>
      </div>
    </div>
  );
}
