import React, { useMemo, useCallback } from 'react';
import ChartHelpTooltip from './ChartHelpTooltip';

interface WeeklyVO2Data {
  week: string;
  vo2_estimate: number | null;
  qualifying_runs: number;
  avg_run_score: number | null;
}

interface WeeklyVO2ChartProps {
  data: WeeklyVO2Data[];
  title?: string;
}

const WeeklyVO2Chart: React.FC<WeeklyVO2ChartProps> = ({
  data,
  title = "VO2 Max Estimates"
}) => {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return { maxVO2: 0, minVO2: 0, avgVO2: 0, validData: false };
    }

    const validData = data.filter(week => week.vo2_estimate !== null && week.vo2_estimate > 0);

    if (validData.length === 0) {
      return { maxVO2: 0, minVO2: 0, avgVO2: 0, validData: false };
    }

    const vo2Values = validData.map(week => week.vo2_estimate!);
    const maxVO2 = Math.max(...vo2Values);
    const minVO2 = Math.min(...vo2Values);
    const avgVO2 = vo2Values.reduce((sum, val) => sum + val, 0) / vo2Values.length;

    return {
      maxVO2,
      minVO2,
      avgVO2,
      validData: true,
      validDataCount: validData.length
    };
  }, [data]);

  const getBarHeight = useCallback((vo2_estimate: number | null) => {
    if (!vo2_estimate || vo2_estimate <= 0 || !chartData.validData) {
      return 20; // Minimum height for empty bars
    }

    const heightPercentage = (vo2_estimate / chartData.maxVO2) * 100;
    return Math.max(heightPercentage * 1.2 + 20, 20); // Dynamic height with minimum
  }, [chartData]);

  const formatVO2Value = useCallback((value: number | null) => {
    if (!value || value <= 0) return 'N/A';
    return Math.round(value).toLocaleString();
  }, []);

  if (!chartData.validData) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100 relative">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-semibold text-gray-800">{title}</h3>
            <ChartHelpTooltip helpContent={{
              title: "VO2 Max Estimates",
              quickTip: "Weekly fitness progression based on your best aerobic performance each week!",
              detailedExplanation: {
                why: "VO2 max estimates track your aerobic fitness improvements over time using your best runs.",
                benefits: [
                  "Shows fitness progression objectively",
                  "Helps set realistic training goals",
                  "Tracks aerobic capacity improvements"
                ],
                tips: [
                  "Higher scores = better aerobic fitness",
                  "Track trends over 4-6 weeks",
                  "Consistency beats single great runs"
                ]
              }
            }} />
          </div>
        </div>
        <div className="flex items-center justify-center h-48 text-gray-500">
          <p>No qualifying runs found for VO2 estimation</p>
        </div>
      </div>
    );
  }

  const { maxVO2, avgVO2, validDataCount } = chartData;

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100 relative">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-3">
          <h3 className="text-xl font-semibold text-gray-800">{title}</h3>
          <ChartHelpTooltip helpContent={{
            title: "VO2 Max Estimates",
            quickTip: "Weekly fitness progression based on your best aerobic performance each week!",
            detailedExplanation: {
              why: "VO2 max estimates track your aerobic fitness improvements over time using your best runs.",
              benefits: [
                "Shows fitness progression objectively",
                "Helps set realistic training goals",
                "Tracks aerobic capacity improvements"
              ],
              tips: [
                "Higher scores = better aerobic fitness",
                "Track trends over 4-6 weeks",
                "Consistency beats single great runs"
              ]
            }
          }} />
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-600">
            <div className="flex gap-4">
              <span>Max: <span className="font-medium text-blue-600">{formatVO2Value(maxVO2)}</span></span>
              <span>Avg: <span className="font-medium text-blue-600">{formatVO2Value(avgVO2)}</span></span>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {/* Chart Bars */}
        <div className="flex items-end justify-between gap-1 h-48 px-2">
          {data.map((week, index) => {
            const isCurrentWeek = index === 0;
            const barHeight = getBarHeight(week.vo2_estimate);
            const hasData = week.vo2_estimate !== null && week.vo2_estimate > 0;

            return (
              <div key={week.week} className="flex-1 flex flex-col items-center group relative">
                {/* VO2 Value Tooltip */}
                {hasData && (
                  <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none whitespace-nowrap z-10 shadow-lg">
                    <div className="text-center">
                      <div className="font-medium">{week.week}</div>
                      <div>VO2: {formatVO2Value(week.vo2_estimate)}</div>
                      <div className="text-gray-300">{week.qualifying_runs} runs</div>
                    </div>
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-gray-800"></div>
                  </div>
                )}

                {/* Bar */}
                <div
                  className={`
                    w-full rounded-t-lg transition-all duration-200 group-hover:shadow-md
                    ${isCurrentWeek
                      ? 'bg-gradient-to-t from-blue-600 to-blue-500 ring-2 ring-blue-300'
                      : hasData
                        ? 'bg-gradient-to-t from-blue-500 to-blue-400 hover:from-blue-600 hover:to-blue-500'
                        : 'bg-gray-200'
                    }
                    ${isCurrentWeek ? 'min-h-8' : ''}
                  `}
                  style={{
                    height: `${barHeight}px`,
                    minHeight: hasData ? '20px' : '8px'
                  }}
                />

                {/* Week Label */}
                <div className="text-xs text-gray-500 mt-2 text-center leading-tight">
                  {week.week.split('-').slice(1).join('/')}
                </div>
              </div>
            );
          })}
        </div>

        {/* Stats Summary */}
        <div className="flex justify-between items-center pt-4 border-t border-gray-100">
          <div className="text-sm text-gray-600">
            Based on {validDataCount} weeks with qualifying runs (≥2 miles, ≥12 min)
          </div>
          <div className="text-xs text-gray-500">
            Higher scores = better aerobic fitness
          </div>
        </div>
      </div>
    </div>
  );
};

export default WeeklyVO2Chart;
