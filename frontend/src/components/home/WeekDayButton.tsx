/**
 * WeekDayButton Component
 * Optimized button for week timeline days
 */
import React, { memo } from 'react';
import { format } from 'date-fns';
import { getDayButtonClasses, getDayNumberClasses, getDayNameClasses, WEEK_TIMELINE_STYLES } from '../../utils/weekTimelineStyles';

interface WeekDayButtonProps {
  date: Date;
  dateStr: string;
  isSelected: boolean;
  isCompleted: boolean;
  isRestDay: boolean;
  workout?: {
    miles: number;
    workout_type: string;
  };
  onClick: (dateStr: string) => void;
}

const WeekDayButton: React.FC<WeekDayButtonProps> = memo(({
  date,
  dateStr,
  isSelected,
  isCompleted,
  isRestDay,
  workout,
  onClick,
}) => {
  // Show full day name on larger screens, single letter on mobile
  const dayNameFull = format(date, 'EEE').toUpperCase();
  const dayNameShort = format(date, 'E').toUpperCase(); // Single letter (M, T, W, etc.)
  const dayNum = format(date, 'd');

  const handleClick = () => {
    onClick(dateStr);
  };

  return (
    <button
      onClick={handleClick}
      className={getDayButtonClasses(isSelected, isCompleted, isRestDay)}
      aria-label={`${dayNameFull} ${dayNum}${workout ? ` - ${workout.workout_type}` : ''}`}
      aria-pressed={isSelected}
    >
      <div className={getDayNameClasses(isRestDay)}>
        <span className="hidden sm:inline">{dayNameFull}</span>
        <span className="sm:hidden">{dayNameShort}</span>
      </div>
      <div className={getDayNumberClasses(isCompleted, isRestDay)}>
        {dayNum}
      </div>

      {/* Status indicator - show checkmark if completed (including rest days with activities) */}
      {isCompleted && (
        <div className={WEEK_TIMELINE_STYLES.indicatorCompleted}>✓</div>
      )}
    </button>
  );
});

WeekDayButton.displayName = 'WeekDayButton';

export default WeekDayButton;
