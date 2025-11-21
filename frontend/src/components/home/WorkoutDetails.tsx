/**
 * WorkoutDetails Component
 * Shows workout details for selected day
 */
import React, { memo } from 'react';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';
import { WEEK_TIMELINE_STYLES } from '../../utils/weekTimelineStyles';
import { normalizeWorkoutTypeDisplay } from '../../utils/workoutTypeUtils';

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
  nextWorkoutDay,
}) => {
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
  if (isRestDay) {
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
                {activity.distance_miles.toFixed(1)} miles
              </div>
              <div className={WEEK_TIMELINE_STYLES.comparisonSubValue}>
                {activity.moving_time && activity.distance_miles > 0
                  ? (() => {
                      const secondsPerMile = activity.moving_time / activity.distance_miles;
                      const minutes = Math.floor(secondsPerMile / 60);
                      const seconds = Math.floor(secondsPerMile % 60);
                      return `Actual Pace: ${minutes}:${seconds.toString().padStart(2, '0')}/mi`;
                    })()
                  : 'Actual Pace: N/A'}
              </div>
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
              {format(nextWorkoutDay.date, 'EEEE')} - {nextWorkoutDay.workout.workout_type} • {nextWorkoutDay.workout.miles} miles
            </p>
          </div>
        )}
      </div>
    );
  }

  if (!workout) {
    return (
      <div>
        <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
          {format(date, 'EEEE, MMMM d')}
        </h3>
        <p className={WEEK_TIMELINE_STYLES.detailsText}>No workout planned for this day.</p>
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
              {workout.miles} miles
            </div>
            {workout.target_zone && (
              <div className={WEEK_TIMELINE_STYLES.comparisonSubValue}>
                Target Pace: {workout.target_zone}
              </div>
            )}
          </div>
          <div className={WEEK_TIMELINE_STYLES.comparisonColumn}>
            <div className={WEEK_TIMELINE_STYLES.comparisonHeader}>Actual</div>
            <div className={WEEK_TIMELINE_STYLES.comparisonValue}>
              {activity.distance_miles.toFixed(1)} miles
            </div>
            <div className={WEEK_TIMELINE_STYLES.comparisonSubValue}>
              {activity.moving_time && activity.distance_miles > 0
                ? (() => {
                    // Calculate pace: seconds per mile
                    const secondsPerMile = activity.moving_time / activity.distance_miles;
                    const minutes = Math.floor(secondsPerMile / 60);
                    const seconds = Math.floor(secondsPerMile % 60);
                    return `Actual Pace: ${minutes}:${seconds.toString().padStart(2, '0')}/mi`;
                  })()
                : 'Actual Pace: N/A'}
            </div>
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
          {workout.miles} miles
        </div>
        {workout.target_zone && (
          <div className="text-sm text-gray-600 mt-1">
            Target Pace: {workout.target_zone}
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
              let targetStr = '';
              if (step.target) {
                const formatPace = (sec: number) => {
                  const min = Math.floor(sec / 60);
                  const secRemainder = Math.round(sec % 60);
                  return `${min}:${secRemainder.toString().padStart(2, '0')}`;
                };
                if (step.target.low && step.target.high) {
                  targetStr = `${formatPace(step.target.low)}–${formatPace(step.target.high)}/mi`;
                } else if (step.target.low) {
                  targetStr = `${formatPace(step.target.low)}/mi`;
                }
              }

              const distanceValue = step.value;
              const distanceUnit = step.durationType === 'DISTANCE' ? (distanceValue === 1 ? 'mile' : 'miles') : (distanceValue === 1 ? 'minute' : 'minutes');
              const intensity = step.intensity || '';

              return (
                <div key={idx} className={WEEK_TIMELINE_STYLES.workoutStructureCard}>
                  <div className={WEEK_TIMELINE_STYLES.workoutStructureCardName}>
                    {step.name}
                  </div>
                  <div className={WEEK_TIMELINE_STYLES.workoutStructureCardDetails}>
                    <span className={WEEK_TIMELINE_STYLES.workoutStructureCardDetailItem}>
                      {distanceValue} {distanceUnit}
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
