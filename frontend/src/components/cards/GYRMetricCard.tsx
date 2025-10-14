import React from 'react';
import {
  GYR_CARD_TEMPLATE,
  getCardClasses,
  getBarClasses,
  getBarStyles,
  getLegendSquareClasses,
  generateBarTooltip
} from '../../utils/gyrCardUtils';

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

export default function GYRMetricCard({
  title,
  historicalScores,
  greenCriteria,
  yellowCriteria,
  redCriteria
}: GYRMetricCardProps) {
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
              title={generateBarTooltip(score, index)}
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
    </div>
  );
}
