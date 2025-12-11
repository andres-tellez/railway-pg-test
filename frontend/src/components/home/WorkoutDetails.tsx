/**
 * WorkoutDetails Component
 * Improved workout details with visual range bars for pace and heart rate
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
  average_heartrate?: number; // Add HR data
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

// Helper to parse pace string to seconds
function parsePaceStringToSeconds(paceStr: string): number {
  const [minutes, seconds] = paceStr.split(':').map(Number);
  return (minutes * 60) + (seconds || 0);
}

// Helper to parse pace range from target_zone
function parsePaceRange(targetZone?: string, unitSystem: 'imperial' | 'metric' = 'imperial'): { min: number; max: number } | null {
  if (!targetZone) return null;

  // Handle range format: "9:23—9:53/mi" or "9:30-10:00/min/mi"
  const rangeMatch = targetZone.match(/^(\d+:\d+)[-–—](\d+:\d+)\/(?:min\/)?(mi|km)$/);

  if (rangeMatch) {
    const [, minPace, maxPace, originalUnit] = rangeMatch;
    const minSeconds = parsePaceStringToSeconds(minPace);
    const maxSeconds = parsePaceStringToSeconds(maxPace);

    // Convert to seconds per mile
    const SEC_PER_MI_TO_SEC_PER_KM = 0.621371;
    const minSecondsPerMile = originalUnit === 'mi'
      ? minSeconds
      : minSeconds / SEC_PER_MI_TO_SEC_PER_KM;
    const maxSecondsPerMile = originalUnit === 'mi'
      ? maxSeconds
      : maxSeconds / SEC_PER_MI_TO_SEC_PER_KM;

    // Convert to display unit if needed
    if (unitSystem === 'metric') {
      return {
        min: minSecondsPerMile * SEC_PER_MI_TO_SEC_PER_KM,
        max: maxSecondsPerMile * SEC_PER_MI_TO_SEC_PER_KM,
      };
    }

    return {
      min: minSecondsPerMile,
      max: maxSecondsPerMile,
    };
  }

  return null;
}

// Helper to parse HR range from target_hr
function parseHRRange(targetHr?: string): { min: number; max: number; zone: string } | null {
  if (!targetHr) return null;

  // Handle format: "Z2 (120–150 bpm)" or "Z2 (120-150 bpm)" or "Z2-Z3 (120–150 bpm)"
  // Note: Backend uses en dash (–) but we also support hyphen (-) for flexibility
  const hrMatch = targetHr.match(/(\d+)[–-](\d+)\s*bpm/);
  const zoneMatch = targetHr.match(/Z[1-5](-Z[1-5])?/);

  if (hrMatch) {
    return {
      min: parseInt(hrMatch[1], 10),
      max: parseInt(hrMatch[2], 10),
      zone: zoneMatch ? zoneMatch[0] : '',
    };
  }

  return null;
}

// Helper to determine status
function getPaceStatus(actualPaceSeconds: number, targetRange: { min: number; max: number }): { status: 'perfect' | 'close' | 'off'; icon: string; label: string } {
  const diff = actualPaceSeconds - targetRange.min;
  const range = targetRange.max - targetRange.min;
  const percentIntoRange = (diff / range) * 100;

  // Within 10% of range edges = close, within range = perfect
  if (actualPaceSeconds >= targetRange.min && actualPaceSeconds <= targetRange.max) {
    return { status: 'perfect', icon: '✓', label: 'Perfect' };
  }

  const tolerance = range * 0.1; // 10% of range
  if (actualPaceSeconds >= targetRange.min - tolerance && actualPaceSeconds <= targetRange.max + tolerance) {
    return { status: 'close', icon: '⚠', label: 'Close' };
  }

  return { status: 'off', icon: '✗', label: 'Off Target' };
}

function getHRStatus(actualHR: number, targetRange: { min: number; max: number }): { status: 'perfect' | 'close' | 'off'; icon: string; label: string } {
  if (actualHR >= targetRange.min && actualHR <= targetRange.max) {
    return { status: 'perfect', icon: '✓', label: 'In Zone' };
  }

  const tolerance = (targetRange.max - targetRange.min) * 0.1; // 10% of range
  if (actualHR >= targetRange.min - tolerance && actualHR <= targetRange.max + tolerance) {
    return { status: 'close', icon: '⚠', label: 'Close' };
  }

  return { status: 'off', icon: '✗', label: 'Off Zone' };
}

// Helper to format pace without units (just time)
function formatPaceWithoutUnits(seconds: number, unitSystem: 'imperial' | 'metric'): string {
  const secondsPerUnit = unitSystem === 'metric'
    ? seconds * 0.621371
    : seconds;

  const minutes = Math.floor(secondsPerUnit / 60);
  const secs = Math.floor(secondsPerUnit % 60);
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

// Range bar component
const RangeBar: React.FC<{
  min: number;
  max: number;
  actual: number;
  formatValue: (val: number) => string;
  formatValueWithoutUnits?: (val: number) => string; // For pace, format without units
  isPace?: boolean; // For pace, lower is faster (left side), higher is slower (right side)
}> = ({ min, max, actual, formatValue, formatValueWithoutUnits, isPace = false }) => {
  const range = max - min;

  // Determine if actual is within range
  const inRange = actual >= min && actual <= max;

  // Calculate bar width (target range as percentage of total visible range)
  // Extend range by 20% on each side for context
  const extendedMin = min - (range * 0.2);
  const extendedMax = max + (range * 0.2);
  const extendedRange = extendedMax - extendedMin;
  const barStart = ((min - extendedMin) / extendedRange) * 100;
  const barWidth = (range / extendedRange) * 100;
  const markerPosition = ((actual - extendedMin) / extendedRange) * 100;

  // Clamp marker position to visible area (0-100%)
  const clampedMarkerPosition = Math.max(0, Math.min(100, markerPosition));

  // Format actual value (without units for pace)
  const actualValueDisplay = formatValueWithoutUnits ? formatValueWithoutUnits(actual) : formatValue(actual);

  return (
    <div className="mt-3">
      <div className="relative h-10 mb-1">
        {/* Background line */}
        <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gray-300 transform -translate-y-1/2"></div>

        {/* Target range bar */}
        <div
          className="absolute top-1/2 h-2 bg-blue-200 transform -translate-y-1/2 rounded"
          style={{
            left: `${barStart}%`,
            width: `${barWidth}%`,
          }}
        ></div>

        {/* Actual value marker with number above */}
        <div
          className="absolute top-1/2 transform -translate-y-1/2 -translate-x-1/2 z-10"
          style={{ left: `${clampedMarkerPosition}%` }}
        >
          {/* Actual value above marker */}
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-1">
          <div className={`${WEEK_TIMELINE_STYLES.actualValue} whitespace-nowrap ${inRange ? 'text-green-600' : 'text-red-600'}`}>
            {actualValueDisplay}
          </div>
          </div>
          {/* Marker dot */}
          <div className={`w-3 h-3 rounded-full ${inRange ? 'bg-green-500' : 'bg-red-500'} border-2 border-white shadow-md`}></div>
        </div>
      </div>

      {/* Target range labels at bar ends - positioned at actual bar boundaries */}
      <div className="relative h-4">
        <div
          className={`absolute ${WEEK_TIMELINE_STYLES.rangeLabel} transform -translate-x-1/2`}
          style={{ left: `${barStart}%` }}
        >
          {formatValueWithoutUnits ? formatValueWithoutUnits(min) : formatValue(min)}
        </div>
        <div
          className={`absolute ${WEEK_TIMELINE_STYLES.rangeLabel} transform -translate-x-1/2`}
          style={{ left: `${barStart + barWidth}%` }}
        >
          {formatValueWithoutUnits ? formatValueWithoutUnits(max) : formatValue(max)}
        </div>
      </div>
    </div>
  );
};

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
  const extractHRZone = (target_hr?: string): string => {
    if (!target_hr) return "";
    const zoneMatch = target_hr.match(/Z[1-5](-Z[1-5])?/);
    if (zoneMatch) {
      return zoneMatch[0];
    }
    return "";
  };

  // Memoized formatted values
  const activityDistance = useMemo(() => {
    if (!activity?.distance_miles) return null;
    return formatDistanceNumber(activity.distance_miles, unitSystem);
  }, [activity?.distance_miles, unitSystem]);

  const workoutDistance = useMemo(() => {
    if (!workout?.miles) return null;
    return formatDistanceNumber(workout.miles, unitSystem);
  }, [workout?.miles, unitSystem]);

  const activityPace = useMemo(() => {
    if (!activity?.moving_time || !activity?.distance_miles || activity.distance_miles <= 0) {
      return null;
    }
    const secondsPerMile = activity.moving_time / activity.distance_miles;
    return {
      formatted: formatPace(secondsPerMile, unitSystem),
      seconds: unitSystem === 'metric' ? secondsPerMile * 0.621371 : secondsPerMile,
    };
  }, [activity?.moving_time, activity?.distance_miles, unitSystem]);

  const convertedTargetZone = useMemo(() => {
    if (!workout?.target_zone) return null;
    return parseAndConvertPaceString(workout.target_zone, unitSystem);
  }, [workout?.target_zone, unitSystem]);

  // Parse pace range for visualization
  const paceRange = useMemo(() => {
    if (!workout?.target_zone) return null;
    return parsePaceRange(workout.target_zone, unitSystem);
  }, [workout?.target_zone, unitSystem]);

  // Parse HR range for visualization
  const hrRange = useMemo(() => {
    if (!workout?.target_hr) return null;
    return parseHRRange(workout.target_hr);
  }, [workout?.target_hr]);

  // Get pace status
  const paceStatus = useMemo(() => {
    if (!activityPace || !paceRange) return null;
    return getPaceStatus(activityPace.seconds, paceRange);
  }, [activityPace, paceRange]);

  // Get HR status
  const hrStatus = useMemo(() => {
    if (!activity?.average_heartrate || !hrRange) return null;
    return getHRStatus(activity.average_heartrate, hrRange);
  }, [activity?.average_heartrate, hrRange]);

  // Handle before plan start
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
              Pace: {activityPace.formatted}
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

  // Rest day handling
  if (isRestDay && hasPlan) {
    if (isCompleted && activity) {
      return (
        <div>
          <h3 className={WEEK_TIMELINE_STYLES.detailsTitle}>Rest Day</h3>
          <p className={WEEK_TIMELINE_STYLES.detailsText + ' mb-4 text-base'}>
            No workout planned for {format(date, 'EEEE')}, but you completed an activity.
          </p>
          <div className="mb-4">
            <div className="text-lg font-semibold text-gray-900 mb-2">
              {activity.name || 'Run'}
            </div>
            <div className="text-2xl font-bold text-gray-900 mb-1">
              {activityDistance}
            </div>
            {activityPace && (
              <div className="text-sm text-gray-600">
                Pace: {activityPace.formatted}
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

  // No workout scenarios
  if (!workout) {
    if (activity && activity.distance_miles > 0) {
      if (!hasPlan) {
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
                  Pace: {activityPace.formatted}
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
    }

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

  // Completed workout with new design
  if (isCompleted && activity) {
    const normalizedWorkoutType = normalizeWorkoutTypeDisplay(workout.workout_type || "") || workout.workout_type;
    const hrZone = extractHRZone(workout.target_hr);
    // Display workout type clearly (e.g., "Easy Run" not just "EASY")
    const displayWorkoutType = normalizedWorkoutType ? `${normalizedWorkoutType} Run` : 'Run';

    return (
      <div>
        <h3 className={WEEK_TIMELINE_STYLES.workoutTypeTitle}>
          {displayWorkoutType}{hrZone && ` (Zone ${hrZone.replace(/Z/g, '')})`}
        </h3>

        {/* Distance Card */}
        <div className={WEEK_TIMELINE_STYLES.metricCard}>
          <div className={WEEK_TIMELINE_STYLES.cardHeader + " mb-3"}>
            Distance ({unitSystem === 'metric' ? 'km' : 'mi'})
          </div>
          <div className={WEEK_TIMELINE_STYLES.actualValue + " text-gray-900"}>
            {activityDistance}
            {workout?.miles && (
              <span className="text-sm text-gray-500 font-normal ml-1">
                (planned: {formatDistanceNumber(workout.miles, unitSystem)})
              </span>
            )}
          </div>
        </div>

        {/* Pace Card */}
        {activityPace && paceRange && paceStatus && (
          <div className={WEEK_TIMELINE_STYLES.metricCard}>
            <div className="flex items-center justify-between mb-3">
              <div className={WEEK_TIMELINE_STYLES.cardHeader}>
                Pace ({unitSystem === 'metric' ? 'min/km' : 'min/mi'})
              </div>
              <div className={`flex items-center gap-2 ${paceStatus.status === 'perfect' ? 'text-green-600' : paceStatus.status === 'close' ? 'text-yellow-600' : 'text-red-600'}`}>
                <span className={WEEK_TIMELINE_STYLES.statusIcon}>{paceStatus.icon}</span>
                <span className={WEEK_TIMELINE_STYLES.statusLabel}>{paceStatus.label}</span>
              </div>
            </div>

            <RangeBar
              min={paceRange.min}
              max={paceRange.max}
              actual={activityPace.seconds}
              formatValue={(val) => formatPace(val, unitSystem)}
              formatValueWithoutUnits={(val) => formatPaceWithoutUnits(val, unitSystem)}
              isPace={true}
            />
          </div>
        )}

        {/* Heart Rate Card */}
        {hrRange && (
          <div className={WEEK_TIMELINE_STYLES.metricCard}>
            <div className="flex items-center justify-between mb-3">
              <div className={WEEK_TIMELINE_STYLES.cardHeader}>Heart Rate (bpm)</div>
              {activity.average_heartrate && hrStatus ? (
                <div className={`flex items-center gap-2 ${hrStatus.status === 'perfect' ? 'text-green-600' : hrStatus.status === 'close' ? 'text-yellow-600' : 'text-red-600'}`}>
                  <span className={WEEK_TIMELINE_STYLES.statusIcon}>{hrStatus.icon}</span>
                  <span className={WEEK_TIMELINE_STYLES.statusLabel}>{hrStatus.label}</span>
                </div>
              ) : (
                <div className={`${WEEK_TIMELINE_STYLES.statusLabel} text-gray-500`}>No data</div>
              )}
            </div>

            {activity.average_heartrate ? (
              <RangeBar
                min={hrRange.min}
                max={hrRange.max}
                actual={activity.average_heartrate}
                formatValue={(val) => `${Math.round(val)} bpm`}
                formatValueWithoutUnits={(val) => `${Math.round(val)}`}
                isPace={false}
              />
            ) : (
              // Show target range bar without marker when no data
              (() => {
                const range = hrRange.max - hrRange.min;
                const extendedMin = hrRange.min - (range * 0.2);
                const extendedMax = hrRange.max + (range * 0.2);
                const extendedRange = extendedMax - extendedMin;
                const barStart = ((hrRange.min - extendedMin) / extendedRange) * 100;
                const barWidth = (range / extendedRange) * 100;

                return (
                  <div className="mt-3">
                    <div className="relative h-10 mb-1">
                      {/* Background line */}
                      <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gray-300 transform -translate-y-1/2"></div>

                      {/* Target range bar */}
                      <div
                        className="absolute top-1/2 h-2 bg-blue-200 transform -translate-y-1/2 rounded"
                        style={{
                          left: `${barStart}%`,
                          width: `${barWidth}%`,
                        }}
                      ></div>
                    </div>

                    {/* Target range labels at bar ends */}
                    <div className="relative h-4">
                      <div
                        className={`absolute ${WEEK_TIMELINE_STYLES.rangeLabel} transform -translate-x-1/2`}
                        style={{ left: `${barStart}%` }}
                      >
                        {Math.round(hrRange.min)}
                      </div>
                      <div
                        className={`absolute ${WEEK_TIMELINE_STYLES.rangeLabel} transform -translate-x-1/2`}
                        style={{ left: `${barStart + barWidth}%` }}
                      >
                        {Math.round(hrRange.max)}
                      </div>
                    </div>
                  </div>
                );
              })()
            )}
          </div>
        )}

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

  // Upcoming workout - use same card-based design as completed workouts
  const normalizedWorkoutType = normalizeWorkoutTypeDisplay(workout.workout_type || "") || workout.workout_type;
  const hrZone = extractHRZone(workout.target_hr);
  // Display workout type clearly (e.g., "Easy Run" not just "EASY")
  const displayWorkoutType = normalizedWorkoutType ? `${normalizedWorkoutType} Run` : 'Run';

  return (
    <div>
      <h3 className={WEEK_TIMELINE_STYLES.workoutTypeTitle}>
        {displayWorkoutType}{hrZone && ` (Zone ${hrZone.replace(/Z/g, '')})`}
      </h3>

      {/* Distance Card */}
      <div className={WEEK_TIMELINE_STYLES.metricCard}>
        <div className={WEEK_TIMELINE_STYLES.cardHeader + " mb-3"}>
          Distance ({unitSystem === 'metric' ? 'km' : 'mi'})
        </div>
        <div className={WEEK_TIMELINE_STYLES.actualValue + " text-gray-900"}>
          {workoutDistance}
        </div>
      </div>

      {/* Pace Card */}
      {paceRange && (
        <div className={WEEK_TIMELINE_STYLES.metricCard}>
          <div className={WEEK_TIMELINE_STYLES.cardHeader + " mb-3"}>
            Pace ({unitSystem === 'metric' ? 'min/km' : 'min/mi'})
          </div>

          {/* Show target range bar without marker */}
          {(() => {
            const range = paceRange.max - paceRange.min;
            const extendedMin = paceRange.min - (range * 0.2);
            const extendedMax = paceRange.max + (range * 0.2);
            const extendedRange = extendedMax - extendedMin;
            const barStart = ((paceRange.min - extendedMin) / extendedRange) * 100;
            const barWidth = (range / extendedRange) * 100;

            return (
              <div className="mt-3">
                <div className="relative h-10 mb-1">
                  {/* Background line */}
                  <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gray-300 transform -translate-y-1/2"></div>

                  {/* Target range bar */}
                  <div
                    className="absolute top-1/2 h-2 bg-blue-200 transform -translate-y-1/2 rounded"
                    style={{
                      left: `${barStart}%`,
                      width: `${barWidth}%`,
                    }}
                  ></div>
                </div>

                {/* Target range labels at bar ends */}
                <div className="relative h-4">
                  <div
                    className={`absolute ${WEEK_TIMELINE_STYLES.rangeLabel} transform -translate-x-1/2`}
                    style={{ left: `${barStart}%` }}
                  >
                    {formatPaceWithoutUnits(paceRange.min, unitSystem)}
                  </div>
                  <div
                    className={`absolute ${WEEK_TIMELINE_STYLES.rangeLabel} transform -translate-x-1/2`}
                    style={{ left: `${barStart + barWidth}%` }}
                  >
                    {formatPaceWithoutUnits(paceRange.max, unitSystem)}
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Heart Rate Card */}
      {hrRange && (
        <div className={WEEK_TIMELINE_STYLES.metricCard}>
          <div className={WEEK_TIMELINE_STYLES.cardHeader + " mb-3"}>Heart Rate (bpm)</div>

          {/* Show target range bar without marker */}
          {(() => {
            const range = hrRange.max - hrRange.min;
            const extendedMin = hrRange.min - (range * 0.2);
            const extendedMax = hrRange.max + (range * 0.2);
            const extendedRange = extendedMax - extendedMin;
            const barStart = ((hrRange.min - extendedMin) / extendedRange) * 100;
            const barWidth = (range / extendedRange) * 100;

            return (
              <div className="mt-3">
                <div className="relative h-10 mb-1">
                  {/* Background line */}
                  <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gray-300 transform -translate-y-1/2"></div>

                  {/* Target range bar */}
                  <div
                    className="absolute top-1/2 h-2 bg-blue-200 transform -translate-y-1/2 rounded"
                    style={{
                      left: `${barStart}%`,
                      width: `${barWidth}%`,
                    }}
                  ></div>
                </div>

                {/* Target range labels at bar ends */}
                <div className="relative h-4">
                  <div
                    className={`absolute ${WEEK_TIMELINE_STYLES.rangeLabel} transform -translate-x-1/2`}
                    style={{ left: `${barStart}%` }}
                  >
                    {Math.round(hrRange.min)}
                  </div>
                  <div
                    className={`absolute ${WEEK_TIMELINE_STYLES.rangeLabel} transform -translate-x-1/2`}
                    style={{ left: `${barStart + barWidth}%` }}
                  >
                    {Math.round(hrRange.max)}
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Workout Structure - keep if exists */}
      {workout.segments?.steps && Array.isArray(workout.segments.steps) && (
        <div className={WEEK_TIMELINE_STYLES.detailsDivider}>
          <p className={WEEK_TIMELINE_STYLES.workoutStructureHeader}>Workout Structure:</p>
          <div className={WEEK_TIMELINE_STYLES.workoutStructureCards}>
            {workout.segments.steps.map((step: any, idx: number) => {
              let targetStr = '';
              if (step.target) {
                if (step.target.low && step.target.high) {
                  targetStr = formatPaceRange(step.target.low, step.target.high, unitSystem);
                } else if (step.target.low) {
                  targetStr = formatPace(step.target.low, unitSystem);
                }
              }

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
