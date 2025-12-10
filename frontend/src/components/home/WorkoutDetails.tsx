/**
 * WorkoutDetails Component
 * Shows workout details for selected day
 */
import React, { memo, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';
import { WEEK_TIMELINE_STYLES } from '../../utils/weekTimelineStyles';
import { normalizeWorkoutTypeDisplay } from '../../utils/workoutTypeUtils';
import { useUnitSystem } from '../../context/UnitSystemContext';
import { formatDistanceNumber, formatDistance, formatPace, formatPaceRange, parseAndConvertPaceString } from '../../utils/unitFormatters';

interface Workout {
  date: string;
  workout_type: string;
  miles: number;
  description?: string;
  target_zone?: string;
  target_hr?: string;
  segments?: any;
}

interface Activity {
  activity_id: number;
  date: string;
  distance_miles: number;
  moving_time?: number; // Moving time in seconds
  name: string;
  type?: string;
}

interface WorkoutDetailsProps {
  date: Date;
  dateStr: string;
  workout?: Workout;
  activity?: Activity;
  isCompleted: boolean;
  isRestDay: boolean;
  hasPlan?: boolean;
  planStartDate?: string | null;
  nextWorkoutDay?: {
    date: Date;
    workout: Workout;
  };
}

const WorkoutDetails: React.FC<WorkoutDetailsProps> = memo(({
  date,
  dateStr,
  workout,
  activity,
  isCompleted,
  isRestDay,
  hasPlan = true,
  planStartDate,
  nextWorkoutDay,
}) => {
  const { unitSystem } = useUnitSystem();

  // Check if this date is before the plan starts
  const isBeforePlanStart = planStartDate && dateStr < planStartDate;

  // Helper to extract just the HR zone (Z1, Z2, etc.) from target_hr
  // Note: target_zone contains pace, not HR zone
  const extractHRZone = (target_hr?: string): string => {
    if (!target_hr) return "";

    // Handle different formats:
    // - "Z2 (120-150 bpm)"
    // - "Z2-Z3 (120-150 bpm)"
    // - "Z2"
    // - "Z2-Z3"
    const zoneMatch = target_hr.match(/Z[1-5](-Z[1-5])?/);
    if (zoneMatch) {
      return zoneMatch[0];
    }

    return "";
  };

  // Memoized formatted values - only recalculate when inputs change
  const activityDistance = useMemo(() => {
    if (!activity?.distance_miles) return null;
    return formatDistance(activity.distance_miles, unitSystem, 1);
  }, [activity?.distance_miles, unitSystem]);

  const workoutDistance = useMemo(() => {
    if (!workout?.miles) return null;
    const formatted = formatDistanceNumber(workout.miles, unitSystem);
    return `${formatted} ${unitSystem === 'metric' ? 'km' : 'mi'}`;
  }, [workout?.miles, unitSystem]);

  const activityPace = useMemo(() => {
    if (!activity?.moving_time || !activity?.distance_miles || activity.distance_miles <= 0) {
      return null;
    }
    // Calculate seconds per mile from activity data
    const secondsPerMile = activity.moving_time / activity.distance_miles;
    return formatPace(secondsPerMile, unitSystem);
  }, [activity?.moving_time, activity?.distance_miles, unitSystem]);

  const convertedTargetZone = useMemo(() => {
    if (!workout?.target_zone) return null;
    return parseAndConvertPaceString(workout.target_zone, unitSystem);
  }, [workout?.target_zone, unitSystem]);
  // If date is before plan starts, show simple activity card without comparison grid
  if (isBeforePlanStart && activity && activity.distance_miles > 0) {
    return (
      <div>
        <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
          {format(date, 'EEEE, MMMM d')}
        </h3>

        <div className="mb-4">
          <div className="text-lg font-semibold text-gray-900 mb-2">
            {activity.name || 'Run'}
          </div>
          <div className="text-2xl font-bold text-gray-900 mb-1">
            {activityDistance}
          </div>
          {activityPace && (
            <div className="text-sm text-gray-600">
              Pace: {activityPace}
            </div>
          )}
        </div>

        <a
          href={`https://www.strava.com/activities/${activity.activity_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className={WEEK_TIMELINE_STYLES.link}
        >
          View activity on Strava →
        </a>
      </div>
    );
  }

  // If date is before plan starts and no activity, show simple message
  if (isBeforePlanStart) {
    return (
      <div>
        <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
          {format(date, 'EEEE, MMMM d')}
        </h3>
        <p className={WEEK_TIMELINE_STYLES.detailsText + ' mb-4 text-base'}>
          No activity recorded for this day.
        </p>
      </div>
    );
  }

  // Only show rest day messaging when there's a plan and date is not before plan start
  if (isRestDay && hasPlan) {
    // If there's an activity on a rest day, show it
    if (isCompleted && activity) {
      return (
        <div>
          <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
            Rest Day
          </h3>
          <p className={WEEK_TIMELINE_STYLES.detailsText + ' mb-4 text-base'}>
            No workout planned for {format(date, 'EEEE')}, but you completed an activity.
          </p>

          {/* Show activity details */}
          <div className={WEEK_TIMELINE_STYLES.comparisonGrid}>
            <div className={WEEK_TIMELINE_STYLES.comparisonColumn}>
              <div className={WEEK_TIMELINE_STYLES.comparisonHeader}>Planned</div>
              <div className={WEEK_TIMELINE_STYLES.comparisonValue}>
                Rest Day
              </div>
            </div>
            <div className={WEEK_TIMELINE_STYLES.comparisonColumn}>
              <div className={WEEK_TIMELINE_STYLES.comparisonHeader}>Actual</div>
              <div className={WEEK_TIMELINE_STYLES.comparisonValue}>
                {activityDistance}
              </div>
              {activityPace && (
                <div className={WEEK_TIMELINE_STYLES.comparisonSubValue}>
                  Actual Pace: {activityPace}
                </div>
              )}
            </div>
          </div>

          {/* Strava link */}
          <a
            href={`https://www.strava.com/activities/${activity.activity_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className={WEEK_TIMELINE_STYLES.link}
          >
            View activity on Strava →
          </a>
        </div>
      );
    }

    // No activity on rest day - show default rest day message
    return (
      <div>
        <h3 className={WEEK_TIMELINE_STYLES.detailsTitle + ' mb-4'}>Rest Day</h3>
        <p className={WEEK_TIMELINE_STYLES.detailsText + ' mb-4 text-base'}>
          No workout planned for {format(date, 'EEEE')}. Use this time to recover and prepare for your next run.
        </p>
        {workout?.description && (
          <p className="text-sm text-gray-500 italic">{workout.description}</p>
        )}
        {nextWorkoutDay && (
          <div className={WEEK_TIMELINE_STYLES.detailsDivider}>
            <p className="text-sm text-gray-600 mb-1">Next workout:</p>
            <p className="text-sm font-medium text-gray-900">
              {format(nextWorkoutDay.date, 'EEEE')} - {nextWorkoutDay.workout.workout_type} • {formatDistanceNumber(nextWorkoutDay.workout.miles, unitSystem)} {unitSystem === 'metric' ? 'km' : 'mi'}
            </p>
          </div>
        )}
      </div>
    );
  }

  if (!workout) {
    // If there's an activity but no workout, show the activity details
    if (activity && activity.distance_miles > 0) {
      // Different layout and messaging for no-plan vs plan-without-workout
      if (!hasPlan) {
        // No plan scenario - simple, clean activity display
        return (
          <div>
            <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
              {format(date, 'EEEE, MMMM d')}
            </h3>

            <div className="mb-4">
              <div className="text-lg font-semibold text-gray-900 mb-2">
                {activity.name || 'Run'}
              </div>
              <div className="text-2xl font-bold text-gray-900 mb-1">
                {activityDistance}
              </div>
              {activityPace && (
                <div className="text-sm text-gray-600">
                  Pace: {activityPace}
                </div>
              )}
            </div>

            {/* Strava link */}
            <a
              href={`https://www.strava.com/activities/${activity.activity_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className={WEEK_TIMELINE_STYLES.link}
            >
              View activity on Strava →
            </a>
          </div>
        );
      } else {
        // Plan exists but no workout this day - use comparison layout
        return (
          <div>
            <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
              {format(date, 'EEEE, MMMM d')}
            </h3>
            <p className={WEEK_TIMELINE_STYLES.detailsText + ' mb-4 text-base'}>
              No workout planned for this day, but you completed an activity.
            </p>

            {/* Show activity details */}
            <div className={WEEK_TIMELINE_STYLES.comparisonGrid}>
              <div className={WEEK_TIMELINE_STYLES.comparisonColumn}>
                <div className={WEEK_TIMELINE_STYLES.comparisonHeader}>Activity</div>
                <div className={WEEK_TIMELINE_STYLES.comparisonValue}>
                  {activityDistance}
                </div>
                <div className={WEEK_TIMELINE_STYLES.comparisonSubValue}>
                  {activityPace ? `Pace: ${activityPace}` : 'Pace: N/A'}
                </div>
                {activity.name && (
                  <div className="text-sm text-gray-600 mt-2">
                    {activity.name}
                  </div>
                )}
              </div>
            </div>

            {/* Strava link */}
            <a
              href={`https://www.strava.com/activities/${activity.activity_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className={WEEK_TIMELINE_STYLES.link}
            >
              View activity on Strava →
            </a>
          </div>
        );
      }
    }

    // No workout and no activity
    return (
      <div>
        <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
          {format(date, 'EEEE, MMMM d')}
        </h3>
        <p className={WEEK_TIMELINE_STYLES.detailsText}>
          {hasPlan ? 'No workout planned for this day.' : 'No activity recorded for this day.'}
        </p>
      </div>
    );
  }

  if (isCompleted && activity) {
    const normalizedWorkoutType = normalizeWorkoutTypeDisplay(workout.workout_type || "") || workout.workout_type;
    const hrZone = extractHRZone(workout.target_hr);

    // Debug logging
    if (process.env.NODE_ENV === 'development') {
      console.log('WorkoutDetails - Completed workout:', {
        workout_type: workout.workout_type,
        target_hr: workout.target_hr,
        target_zone: workout.target_zone,
        extracted_hrZone: hrZone,
      });
    }

    return (
      <div>
        <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
          {normalizedWorkoutType}{hrZone && ` (${hrZone})`}
        </h3>

        {/* Side-by-side comparison */}
        <div className={WEEK_TIMELINE_STYLES.comparisonGrid}>
          <div className={WEEK_TIMELINE_STYLES.comparisonColumn}>
            <div className={WEEK_TIMELINE_STYLES.comparisonHeader}>Planned</div>
            <div className={WEEK_TIMELINE_STYLES.comparisonValue}>
              {workoutDistance}
            </div>
            {convertedTargetZone && (
              <div className={`${WEEK_TIMELINE_STYLES.comparisonSubValue} flex items-center gap-1`}>
                Target Pace: {convertedTargetZone}
                <Link
                  to="/pace-zones"
                  className="text-blue-600 hover:text-blue-800"
                  title="Learn about pace zones"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </Link>
              </div>
            )}
          </div>
          <div className={WEEK_TIMELINE_STYLES.comparisonColumn}>
            <div className={WEEK_TIMELINE_STYLES.comparisonHeader}>Actual</div>
            <div className={WEEK_TIMELINE_STYLES.comparisonValue}>
              {activityDistance}
            </div>
            {activityPace && (
              <div className={WEEK_TIMELINE_STYLES.comparisonSubValue}>
                Actual Pace: {activityPace}
              </div>
            )}
          </div>
        </div>

        {/* Coach's Note */}
        <div className={WEEK_TIMELINE_STYLES.coachNoteSection}>
          <div className={WEEK_TIMELINE_STYLES.coachNoteHeader}>
            <span className={WEEK_TIMELINE_STYLES.coachNoteIcon}>💬</span>
            <h4 className={WEEK_TIMELINE_STYLES.coachNoteTitle}>Coach's Note</h4>
          </div>
          <p className={WEEK_TIMELINE_STYLES.coachNoteText}>
            Analysis coming soon! We'll provide personalized feedback on your workout performance.
          </p>
          <Link to="/ask" className={WEEK_TIMELINE_STYLES.coachNoteLink}>
            Ask the coach about this workout →
          </Link>
        </div>

        {/* Strava link */}
        <a
          href={`https://www.strava.com/activities/${activity.activity_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className={WEEK_TIMELINE_STYLES.link}
        >
          View activity on Strava →
        </a>
      </div>
    );
  }

  // Upcoming workout
  const normalizedWorkoutType = normalizeWorkoutTypeDisplay(workout.workout_type || "") || workout.workout_type;
  const hrZone = extractHRZone(workout.target_hr);

  // Debug logging
  if (process.env.NODE_ENV === 'development') {
    console.log('WorkoutDetails - Upcoming workout:', {
      workout_type: workout.workout_type,
      target_hr: workout.target_hr,
      target_zone: workout.target_zone,
      extracted_hrZone: hrZone,
    });
  }

  return (
    <div>
      <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
        {normalizedWorkoutType}{hrZone && ` (${hrZone})`}
      </h3>
      <div className={WEEK_TIMELINE_STYLES.detailsSection}>
        <div className="text-lg font-medium text-gray-900">
          {workoutDistance}
        </div>
        {convertedTargetZone && (
          <div className="text-sm text-gray-600 mt-1 flex items-center gap-1">
            Target Pace: {convertedTargetZone}
            <Link
              to="/pace-zones"
              className="text-blue-600 hover:text-blue-800"
              title="Learn about pace zones"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </Link>
          </div>
        )}
        {!hrZone && workout.target_hr && (
          <div className="text-sm text-gray-500 text-xs mt-1">
            Debug: target_hr = "{workout.target_hr}"
          </div>
        )}
      </div>
      {workout.segments?.steps && Array.isArray(workout.segments.steps) && (
        <div className={WEEK_TIMELINE_STYLES.detailsDivider}>
          <p className={WEEK_TIMELINE_STYLES.workoutStructureHeader}>Workout Structure:</p>
          <div className={WEEK_TIMELINE_STYLES.workoutStructureCards}>
            {workout.segments.steps.map((step: any, idx: number) => {
              // Format target from spec-compliant format {low: sec, high: sec}
              // These are already in seconds per mile from backend
              let targetStr = '';
              if (step.target) {
                if (step.target.low && step.target.high) {
                  targetStr = formatPaceRange(step.target.low, step.target.high, unitSystem);
                } else if (step.target.low) {
                  targetStr = formatPace(step.target.low, unitSystem);
                }
              }

              // Convert segment distance
              const distanceValue = step.value;
              const isDistance = step.durationType === 'DISTANCE';
              const formattedDistance = isDistance
                ? `${formatDistanceNumber(distanceValue, unitSystem)} ${unitSystem === 'metric' ? 'km' : 'mi'}`
                : `${distanceValue} ${distanceValue === 1 ? 'minute' : 'minutes'}`;

              const intensity = step.intensity || '';

              return (
                <div key={idx} className={WEEK_TIMELINE_STYLES.workoutStructureCard}>
                  <div className={WEEK_TIMELINE_STYLES.workoutStructureCardName}>
                    {step.name}
                  </div>
                  <div className={WEEK_TIMELINE_STYLES.workoutStructureCardDetails}>
                    <span className={WEEK_TIMELINE_STYLES.workoutStructureCardDetailItem}>
                      {formattedDistance}
                    </span>
                    {intensity && (
                      <>
                        <span className="text-gray-400">•</span>
                        <span className={WEEK_TIMELINE_STYLES.workoutStructureCardDetailItem}>
                          {intensity}
                        </span>
                      </>
                    )}
                    {targetStr && (
                      <>
                        <span className="text-gray-400">•</span>
                        <span className={WEEK_TIMELINE_STYLES.workoutStructureCardDetailItem}>
                          {targetStr}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
});

WorkoutDetails.displayName = 'WorkoutDetails';

export default WorkoutDetails;
