import React from 'react';

interface GYRScore {
  value: number;
  date: string;
  status: 'green' | 'yellow' | 'red' | 'gray';
}

interface GYRMetricCardProps {
  title: string;
  historicalScores: GYRScore[];
  greenCriteria: string;
  yellowCriteria: string;
  redCriteria: string;
}

// Template skeleton structure
const GYRMetricCardTemplate = {
  container: "bg-white rounded-lg shadow-lg px-0 pt-6 border border-gray-100 w-96 min-h-64 flex flex-col",
  header: "mb-2 px-6",
  title: "text-xl font-bold text-gray-900",
  timelineContainer: "flex-1 flex items-center justify-center",
  timelineInner: "flex items-center justify-center gap-3",
  tick: "rounded-sm transition-all duration-200 hover:opacity-80 hover:scale-105 hover:shadow-md cursor-pointer",
  tickSize: { width: '24px', height: '64px' },
  dividerContainer: "mt-4",
  divider: "h-px bg-gradient-to-r from-transparent via-gray-200 to-transparent mb-3",
  legend: "bg-gray-800 rounded-b-lg px-3 pt-3 pb-3 flex gap-3",
  legendItem: "flex items-center gap-1",
  legendSquare: "w-6 h-6 rounded-sm shadow-sm",
  legendText: "text-sm text-white leading-tight"
};

const getStatusColor = (status: string) => {
  switch (status) {
    case 'green': return 'bg-emerald-400';
    case 'yellow': return 'bg-amber-400';
    case 'red': return 'bg-rose-400';
    case 'gray': return 'bg-slate-300';
    default: return 'bg-slate-300';
  }
};

export default function GYRMetricCard({
  title,
  historicalScores,
  greenCriteria,
  yellowCriteria,
  redCriteria
}: GYRMetricCardProps) {
  return (
    <div className={GYRMetricCardTemplate.container}>
      {/* Header */}
      <div className={GYRMetricCardTemplate.header}>
        <h3 className={GYRMetricCardTemplate.title}>{title}</h3>
      </div>

      {/* Timeline Bars - 8 weeks (Middle) */}
      <div className={GYRMetricCardTemplate.timelineContainer}>
        <div className={GYRMetricCardTemplate.timelineInner}>
          {historicalScores.slice(0, 8).map((score, index) => (
            <div
              key={index}
              className={`${GYRMetricCardTemplate.tick} ${getStatusColor(score.status)}`}
              style={GYRMetricCardTemplate.tickSize}
              title={`Week ${index + 1}: ${score.date} - ${score.value}% (${score.status})`}
            />
          ))}
        </div>
      </div>

      {/* Legend Section */}
      <div className={GYRMetricCardTemplate.dividerContainer}>
        {/* Gradient divider */}
        <div className={GYRMetricCardTemplate.divider}></div>

        {/* Legend */}
        <div className={GYRMetricCardTemplate.legend}>
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-emerald-400"></div>
            <div className="text-xs text-white leading-tight">{greenCriteria}</div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-amber-400"></div>
            <div className="text-xs text-white leading-tight">{yellowCriteria}</div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-rose-400"></div>
            <div className="text-xs text-white leading-tight">{redCriteria}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
