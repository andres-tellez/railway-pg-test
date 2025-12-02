/**
 * ProgressBar Component
 * Reusable progress bar for weekly progress
 */
import React, { memo } from 'react';
import { WEEK_TIMELINE_STYLES } from '../../utils/weekTimelineStyles';
import { useUnitSystem } from '../../context/UnitSystemContext';
import { formatDistance, toDisplayDistance } from '../../utils/unitFormatters';

interface ProgressBarProps {
  completed: number;
  total: number;
  milesCompleted: number;
  milesTotal: number;
}

const ProgressBar: React.FC<ProgressBarProps> = memo(({
  completed,
  total,
  milesCompleted,
  milesTotal,
}) => {
  const { unitSystem } = useUnitSystem();
  const percentage = total > 0 ? (completed / total) * 100 : 0;

  // Format distances: show value only for completed, full format for total
  const completedValue = toDisplayDistance(milesCompleted, unitSystem).toFixed(1);
  const totalDistance = formatDistance(milesTotal, unitSystem, 1);

  return (
    <div className={WEEK_TIMELINE_STYLES.progressSection}>
      <div className={WEEK_TIMELINE_STYLES.progressHeader}>
        <span className={WEEK_TIMELINE_STYLES.progressLabel}>Weekly Progress</span>
        <span className={WEEK_TIMELINE_STYLES.progressValue}>
          {completed} / {total} workouts
        </span>
      </div>
      <div className={WEEK_TIMELINE_STYLES.progressBarContainer}>
        <div
          className={WEEK_TIMELINE_STYLES.progressBarFill}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={completed}
          aria-valuemin={0}
          aria-valuemax={total}
        />
      </div>
      <div className={WEEK_TIMELINE_STYLES.progressMiles}>
        {completedValue} / {totalDistance}
      </div>
    </div>
  );
});

ProgressBar.displayName = 'ProgressBar';

export default ProgressBar;
