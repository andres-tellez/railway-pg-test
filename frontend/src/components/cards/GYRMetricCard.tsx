import React, { useState } from 'react';
import {
  GYR_CARD_TEMPLATE,
  getCardClasses,
  getBarClasses,
  getBarStyles,
  getLegendSquareClasses
} from '../../utils/gyrCardUtils';
import { useScrollHideTooltip } from '../../hooks/useScrollHideTooltip';

interface GYRScore {
  value: number;
  date: string;
  status: 'green' | 'yellow' | 'red' | 'gray';
  actual_miles?: number;
  planned_miles?: number;
  actual_runs?: number;
  current_pace?: string;
  avg_pace?: string | null;
  z1_z2_pct?: number;
}

interface GYRMetricCardProps {
  title: string;
  historicalScores: GYRScore[];
  greenCriteria: string;
  yellowCriteria: string;
  redCriteria: string;
  metricType?: 'totalRuns' | 'weeklyPace' | 'weeklyHRZones';
}

export default function GYRMetricCard({
  title,
  historicalScores,
  greenCriteria,
  yellowCriteria,
  redCriteria,
  metricType = 'totalRuns'
}: GYRMetricCardProps) {
  const [hoveredBar, setHoveredBar] = useState<{
    index: number;
    x: number;
    y: number;
    barTop?: number;
    barHeight?: number;
    viewportHeight?: number;
  } | null>(null);

  // Centralized tooltip behavior - hide on scroll
  useScrollHideTooltip(hoveredBar !== null, () => setHoveredBar(null));
  return (
    <div className={getCardClasses()}>
      {/* Header */}
      <div className={GYR_CARD_TEMPLATE.header}>
        <h3 className={GYR_CARD_TEMPLATE.title}>{title}</h3>
      </div>

      {/* Timeline */}
      <div className={GYR_CARD_TEMPLATE.timeline}>
        <div className={GYR_CARD_TEMPLATE.timelineBars}>
          {historicalScores.slice(0, 8).map((score, index) => (
            <div
              key={index}
              className={getBarClasses(score.status)}
              style={getBarStyles()}
                     onMouseEnter={(e) => {
                       const rect = e.currentTarget.getBoundingClientRect();
                       setHoveredBar({
                         index,
                         x: rect.left + rect.width / 2,
                         y: rect.top - 10,
                         // Add viewport info for smart positioning
                         barTop: rect.top,
                         barHeight: rect.height,
                         viewportHeight: window.innerHeight
                       });
                     }}
              onMouseLeave={() => setHoveredBar(null)}
            />
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className={GYR_CARD_TEMPLATE.legend}>
        <div className={GYR_CARD_TEMPLATE.divider}></div>
        <div className={GYR_CARD_TEMPLATE.legendContainer}>
          <div className={GYR_CARD_TEMPLATE.legendItem}>
            <div className={getLegendSquareClasses('green')}></div>
            <div className={GYR_CARD_TEMPLATE.legendText}>{greenCriteria}</div>
          </div>
          <div className={GYR_CARD_TEMPLATE.legendItem}>
            <div className={getLegendSquareClasses('yellow')}></div>
            <div className={GYR_CARD_TEMPLATE.legendText}>{yellowCriteria}</div>
          </div>
          <div className={GYR_CARD_TEMPLATE.legendItem}>
            <div className={getLegendSquareClasses('red')}></div>
            <div className={GYR_CARD_TEMPLATE.legendText}>{redCriteria}</div>
          </div>
        </div>
      </div>

      {/* Custom Tooltip - Same style as bar charts */}
      {hoveredBar && (
        <div
          className="fixed z-50 bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-600 rounded-lg p-3 shadow-2xl pointer-events-none backdrop-blur-sm"
          style={(() => {
            // More robust positioning logic
            const tooltipHeight = 250; // Slightly larger estimate for safety
            const barTop = hoveredBar.barTop || 0;
            const barHeight = hoveredBar.barHeight || 64;
            const viewportHeight = hoveredBar.viewportHeight || window.innerHeight;

            const spaceAbove = barTop;
            const spaceBelow = viewportHeight - barTop - barHeight;

            // Debug logging
            console.log('Tooltip positioning:', {
              barTop,
              spaceAbove,
              spaceBelow,
              tooltipHeight,
              shouldShowBelow: spaceAbove < tooltipHeight + 50
            });

            // Always position below if there's not enough space above
            if (spaceAbove < tooltipHeight + 50) {
              // Position below the bar with some margin
              return {
                left: `${hoveredBar.x}px`,
                top: `${barTop + barHeight + 15}px`,
                transform: 'translate(-50%, 0%)',
                minWidth: '280px',
                maxWidth: '320px',
                backdropFilter: 'blur(8px)',
              };
            } else {
              // Position above the bar with margin from top
              return {
                left: `${hoveredBar.x}px`,
                top: `${Math.max(20, barTop - tooltipHeight - 10)}px`, // Ensure at least 20px from top
                transform: 'translate(-50%, 0%)',
                minWidth: '280px',
                maxWidth: '320px',
                backdropFilter: 'blur(8px)',
              };
            }
          })()}
        >
          {(() => {
            const score = historicalScores[hoveredBar.index];
            const statusEmoji = score.status === 'green' ? '🟢' : score.status === 'yellow' ? '🟡' : score.status === 'red' ? '🔴' : '⚪';


            // Format date
            const formatDate = (dateStr: string) => {
              try {
                const date = dateStr.includes('T') ? new Date(dateStr) : new Date(dateStr + 'T00:00:00');
                return date.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric'
                });
              } catch {
                return dateStr;
              }
            };

            if (metricType === 'totalRuns') {
              const actual = score.actual_miles?.toFixed(1) || '0.0';
              const planned = score.planned_miles?.toFixed(1) || '0.0';
              const runs = score.actual_runs || 0;
              const pct = score.value.toFixed(1);

              if (score.status === 'gray') {
                return (
                  <>
                    <div className="text-white font-bold text-sm mb-2 text-center bg-gray-700/30 rounded px-2 py-1">
                      Week of {formatDate(score.date)}
                    </div>
                    <div className="space-y-1.5 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300">Actual:</span>
                        <span className="text-white font-semibold">{actual} mi ({runs} runs)</span>
                      </div>
                      <div className="mt-2 pt-2 border-t border-gray-600 text-gray-400 font-semibold text-center text-sm bg-gray-900/20 rounded px-2 py-1">
                        No active plan for comparison
                      </div>
                    </div>
                  </>
                );
              }

              let explanation = '';
              let explanationColor = '';
              if (score.status === 'green') {
                explanation = '✓ On track (90-110% of plan)';
                explanationColor = 'text-green-400 bg-green-900/20';
              } else if (score.status === 'yellow') {
                const actualPct = parseFloat(pct);
                explanation = actualPct < 90 ? '⚠ Below plan (70-90%)' : '⚠ Above plan (110-130%)';
                explanationColor = 'text-yellow-400 bg-yellow-900/20';
              } else {
                const actualPct = parseFloat(pct);
                explanation = actualPct < 70 ? '❌ Well below plan (<70%)' : '❌ Well above plan (>130%)';
                explanationColor = 'text-red-400 bg-red-900/20';
              }

              return (
                <>
                  <div className="text-white font-bold text-sm mb-2 text-center bg-gray-700/30 rounded px-2 py-1">
                    Week of {formatDate(score.date)}
                  </div>
                  <div className="space-y-1.5 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300">Actual:</span>
                      <span className="text-white font-semibold">{actual} mi ({runs} runs)</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300">Planned:</span>
                      <span className="text-white font-semibold">{planned} mi</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300">Completion:</span>
                      <span className="text-white font-semibold">{pct}%</span>
                    </div>
                    <div className={`mt-2 pt-2 border-t border-gray-600 font-bold text-center text-sm ${explanationColor} rounded px-2 py-1`}>
                      {explanation}
                    </div>
                  </div>
                </>
              );
            }

            if (metricType === 'weeklyPace') {
              const currentPace = score.current_pace || '0:00';
              const avgPace = score.avg_pace || 'N/A';

              if (score.status === 'gray') {
                return (
                  <>
                    <div className="text-white font-bold text-sm mb-2 text-center bg-gray-700/30 rounded px-2 py-1">
                      Week of {formatDate(score.date)}
                    </div>
                    <div className="space-y-1.5 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300">Pace:</span>
                        <span className="text-white font-semibold">{currentPace}/mi</span>
                      </div>
                      <div className="mt-2 pt-2 border-t border-gray-600 text-gray-400 font-semibold text-center text-sm bg-gray-900/20 rounded px-2 py-1">
                        Insufficient history
                      </div>
                    </div>
                  </>
                );
              }

              let explanation = '';
              let explanationColor = '';
              if (score.status === 'green') {
                explanation = '✓ Same or faster than 3-wk avg';
                explanationColor = 'text-green-400 bg-green-900/20';
              } else if (score.status === 'yellow') {
                explanation = '⚠ Up to 10s/mi slower';
                explanationColor = 'text-yellow-400 bg-yellow-900/20';
              } else {
                explanation = '❌ >10s/mi slower than avg';
                explanationColor = 'text-red-400 bg-red-900/20';
              }

              return (
                <>
                  <div className="text-white font-bold text-sm mb-2 text-center bg-gray-700/30 rounded px-2 py-1">
                    Week of {formatDate(score.date)}
                  </div>
                  <div className="space-y-1.5 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300">Current:</span>
                      <span className="text-white font-semibold">{currentPace}/mi</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300">3-wk Avg:</span>
                      <span className="text-white font-semibold">{avgPace}/mi</span>
                    </div>
                    <div className={`mt-2 pt-2 border-t border-gray-600 font-bold text-center text-sm ${explanationColor} rounded px-2 py-1`}>
                      {explanation}
                    </div>
                  </div>
                </>
              );
            }

            if (metricType === 'weeklyHRZones') {
              const z1z2 = score.z1_z2_pct?.toFixed(1) || '0.0';

              if (score.status === 'gray') {
                return (
                  <>
                    <div className="text-white font-bold text-sm mb-2 text-center bg-gray-700/30 rounded px-2 py-1">
                      Week of {formatDate(score.date)}
                    </div>
                    <div className="space-y-1.5 text-sm">
                      <div className="mt-2 pt-2 border-t border-gray-600 text-gray-400 font-semibold text-center text-sm bg-gray-900/20 rounded px-2 py-1">
                        No HR data available
                      </div>
                    </div>
                  </>
                );
              }

              let explanation = '';
              let explanationColor = '';
              let recommendations = '';

              if (score.status === 'green') {
                explanation = '✓ Perfect 80/20 balance';
                explanationColor = 'text-green-400 bg-green-900/20';
                recommendations = 'Excellent work! You\'re following the optimal training distribution.\n\n' +
                  'BENEFITS YOU\'RE GETTING:\n' +
                  '• Optimal aerobic base development\n' +
                  '• Reduced injury risk\n\n' +
                  'KEEP DOING:\n' +
                  '• Maintain 75-85% easy runs\n' +
                  '• Continue 15-25% hard efforts\n\n' +
                  'WHY THIS WORKS:\n' +
                  '• Builds endurance without overtraining\n' +
                  '• Allows for consistent training';
              } else if (score.status === 'yellow') {
                const actualPct = parseFloat(z1z2);
                if (actualPct < 75) {
                  explanation = '⚠ Need more easy runs';
                  explanationColor = 'text-yellow-400 bg-yellow-900/20';
                  recommendations = 'You\'re close to optimal but need more easy training.\n\n' +
                    'IMMEDIATE ACTIONS:\n' +
                    '• Add 1-2 easy recovery runs this week\n' +
                    '• Focus on conversation pace (Zone 2)\n\n' +
                    'MILD RISKS:\n' +
                    '• Slightly increased injury risk\n' +
                    '• Potential performance plateau\n\n' +
                    'WHY THIS HAPPENS:\n' +
                    '• Running too fast on easy days\n' +
                    '• Not enough recovery between sessions';
                } else {
                  explanation = '⚠ Need more hard runs';
                  explanationColor = 'text-yellow-400 bg-yellow-900/20';
                  recommendations = 'You\'re close to optimal but need more intensity.\n\n' +
                    'IMMEDIATE ACTIONS:\n' +
                    '• Add 1 high-intensity session this week\n' +
                    '• Include intervals or tempo runs\n\n' +
                    'MISSING BENEFITS:\n' +
                    '• Limited speed development\n' +
                    '• Reduced lactate threshold gains\n\n' +
                    'WHY THIS HAPPENS:\n' +
                    '• Avoiding hard training sessions\n' +
                    '• Running everything at moderate effort';
                }
              } else {
                // Red status - detailed recommendations
                const actualPct = parseFloat(z1z2);
                if (actualPct < 65) {
                  explanation = '❌ Need much more easy runs';
                  explanationColor = 'text-red-400 bg-red-900/20';
                  recommendations = '🚨 URGENT: You\'re overtraining! This training load is unsustainable and dangerous.\n\n' +
                    'IMMEDIATE ACTIONS:\n' +
                    '• Replace 2-3 hard runs with easy runs\n' +
                    '• Focus on Zone 2 pace (conversation pace)\n\n' +
                    'SAFETY RISKS:\n' +
                    '• High injury risk from chronic stress\n' +
                    '• Burnout and mental fatigue\n\n' +
                    'WHY THIS HAPPENS:\n' +
                    '• Too much time in Zone 3 (junk miles)\n' +
                    '• Insufficient aerobic base building';
                } else {
                  explanation = '❌ Need much more hard runs';
                  explanationColor = 'text-red-400 bg-red-900/20';
                  recommendations = 'You\'re undertraining intensity! While this is safer than overtraining, you\'re missing key adaptations.\n\n' +
                    'ACTIONS:\n' +
                    '• Add 2-3 high-intensity sessions this week\n' +
                    '• Include intervals, tempo runs, or hill repeats\n\n' +
                    'MISSING BENEFITS:\n' +
                    '• Speed and power development\n' +
                    '• Lactate threshold improvement';
                }
              }

              return (
                <>
                  <div className="text-white font-bold text-sm mb-2 text-center bg-gray-700/30 rounded px-2 py-1">
                    Week of {formatDate(score.date)}
                  </div>
                  <div className="space-y-1.5 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300">Easy (Z1-Z2):</span>
                      <span className="text-white font-semibold">{z1z2}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300">Hard (Z3-Z5):</span>
                      <span className="text-white font-semibold">{(100 - parseFloat(z1z2)).toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300">Target:</span>
                      <span className="text-white font-semibold">80% easy / 20% hard</span>
                    </div>
                    <div className={`mt-2 pt-2 border-t border-gray-600 font-bold text-center text-sm ${explanationColor} rounded px-2 py-1`}>
                      {explanation}
                    </div>
                    <div className="mt-3 pt-3 border-t border-gray-600">
                      <div className="text-xs text-gray-300 font-semibold mb-2 flex items-center">
                        <span className="mr-1">💡</span>
                        Recommendations
                      </div>
                      <div className="text-xs text-gray-200 leading-relaxed bg-gray-800/30 rounded p-2 whitespace-pre-line">
                        {recommendations}
                      </div>
                    </div>
                  </div>
                </>
              );
            }

            return null;
          })()}
        </div>
      )}
    </div>
  );
}
