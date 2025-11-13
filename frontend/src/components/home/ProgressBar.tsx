/**
 * ProgressBar Component
 * Reusable progress bar for weekly progress
 */
import React, { memo } from 'react';
import { WEEK_TIMELINE_STYLES } from '../../utils/weekTimelineStyles';

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
  const percentage = total > 0 ? (completed / total) * 100 : 0;

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
        {milesCompleted.toFixed(1)} / {milesTotal.toFixed(1)} miles
      </div>
    </div>
  );
});

ProgressBar.displayName = 'ProgressBar';

export default ProgressBar;
