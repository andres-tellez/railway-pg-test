/**
 * WorkoutDetails Component
 * Shows workout details for selected day
 */
import React, { memo } from 'react';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';
import { WEEK_TIMELINE_STYLES } from '../../utils/weekTimelineStyles';

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
  name: string;
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
  if (isRestDay) {
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
    return (
      <div>
        <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
          {workout.workout_type}
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
                {workout.target_zone}
              </div>
            )}
          </div>
          <div className={WEEK_TIMELINE_STYLES.comparisonColumn}>
            <div className={WEEK_TIMELINE_STYLES.comparisonHeader}>Actual</div>
            <div className={WEEK_TIMELINE_STYLES.comparisonValue}>
              {activity.distance_miles.toFixed(1)} miles
            </div>
            <div className={WEEK_TIMELINE_STYLES.comparisonSubValue}>
              Pace: N/A
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
  return (
    <div>
      <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>
        {workout.workout_type}
      </h3>
      <div className={WEEK_TIMELINE_STYLES.detailsSection}>
        <div className="text-lg font-medium text-gray-900">
          {workout.miles} miles
        </div>
        {workout.target_hr && (
          <div className="text-sm text-gray-600">
            Target HR: {workout.target_hr}
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
