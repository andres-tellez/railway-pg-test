/**
 * Week Timeline Utility Functions
 *
 * One-to-One Assignment Pattern:
 * - Activities are assigned to days using a deduplication set
 * - Each activity can only be assigned once (prevents duplicates)
 * - Priority: Exact date match > Workout match with tolerance
 */

import { toDateString, dateStringToDate, compareDates, isToday, getWeekDateStrings } from './dateUtils';

export interface Workout {
  date: string; // YYYY-MM-DD format
  workout_type: string;
  miles: number;
  description?: string;
  target_zone?: string;
  target_hr?: string;
  segments?: any;
}

export interface Activity {
  activity_id: number;
  date: string; // YYYY-MM-DD format (normalized)
  distance_miles: number;
  moving_time?: number; // Moving time in seconds
  name: string;
  type: string;
}

export interface WeekDay {
  dateStr: string; // YYYY-MM-DD - PRIMARY identifier
  date: Date; // For display/formatting only
  workout?: Workout;
  activity?: Activity;
  isCompleted: boolean;
  isRestDay: boolean;
  isToday: boolean;
}

/**
 * Check if activity matches workout criteria (±1 day, ±30% distance)
 *
 * @internal - Exported for testing purposes only
 */
export function matchesWorkout(activity: Activity, workout: Workout): boolean {
  const activityDate = toDateString(activity.date);
  const workoutDate = toDateString(workout.date);

  // Date check: allow ±1 day tolerance
  const daysDiff = Math.abs(compareDates(activityDate, workoutDate));
  if (daysDiff > 1) return false;

  // Distance check: ±30% tolerance
  const distanceDiff = Math.abs(activity.distance_miles - workout.miles) / Math.max(workout.miles, 0.1);
  return distanceDiff <= 0.3;
}

/**
 * Process week data with one-to-one activity assignment.
 *
 * Assignment Strategy:
 * 1. First pass: Assign activities to their exact date (highest priority)
 * 2. Second pass: For unmatched workouts, find best matching activity from remaining pool
 *
 * Prevents duplicate assignments using a deduplication set.
 */
export function processWeekData(
  workouts: Workout[],
  activities: Activity[],
  weekStart: string, // YYYY-MM-DD
  weekEnd: string    // YYYY-MM-DD
): WeekDay[] {
  // Normalize all inputs to date-only strings
  const normalizedActivities: Activity[] = activities.map(act => ({
    ...act,
    date: toDateString(act.date),
  }));

  const normalizedWorkouts: Workout[] = workouts.map(w => ({
    ...w,
    date: toDateString(w.date),
  }));

  // Generate week days
  const weekDays = getWeekDateStrings(weekStart);

  // Deduplication set: track which activities have been assigned
  const matchedActivityIds = new Set<number>();

  // First pass: Assign activities to exact dates
  const dayAssignments = new Map<string, Activity>();

  for (const dateStr of weekDays) {
    // Find unassigned activity on this exact date
    const exactMatch = normalizedActivities.find(act =>
      act.date === dateStr && !matchedActivityIds.has(act.activity_id)
    );

    if (exactMatch) {
      dayAssignments.set(dateStr, exactMatch);
      matchedActivityIds.add(exactMatch.activity_id);
    }
  }

  // Second pass: Assign remaining activities to workouts (if no exact match)
  for (const dateStr of weekDays) {
    // Skip if already assigned in first pass
    if (dayAssignments.has(dateStr)) continue;

    const workout = normalizedWorkouts.find(w => w.date === dateStr);
    if (!workout) continue;

    // Find best matching unassigned activity
    const workoutMatch = normalizedActivities.find(act =>
      !matchedActivityIds.has(act.activity_id) &&
      matchesWorkout(act, workout)
    );

    if (workoutMatch) {
      dayAssignments.set(dateStr, workoutMatch);
      matchedActivityIds.add(workoutMatch.activity_id);
    }
  }

  // Build result array
  return weekDays.map(dateStr => {
    const workout = normalizedWorkouts.find(w => w.date === dateStr);
    const activity = dayAssignments.get(dateStr);

    return {
      dateStr,
      date: dateStringToDate(dateStr), // For display only
      workout,
      activity,
      isCompleted: !!activity,
      isRestDay: !workout || workout.workout_type?.toLowerCase().includes('rest'),
      isToday: isToday(dateStr),
    };
  });
}

/**
 * Get this week's range (returns date strings)
 * Re-export from dateUtils for convenience
 */
export { getThisWeekRange } from './dateUtils';

/**
 * Calculate weekly progress
 */
export function calculateWeeklyProgress(weekDays: WeekDay[]): {
  completed: number;
  total: number;
  milesCompleted: number;
  milesTotal: number;
} {
  const completedWorkouts = weekDays.filter(d => d.isCompleted && !d.isRestDay).length;
  const totalWorkouts = weekDays.filter(d => !d.isRestDay && d.workout).length;

  const milesCompleted = weekDays
    .filter(d => d.isCompleted && d.activity)
    .reduce((sum, d) => sum + (d.activity?.distance_miles || 0), 0);

  const milesTotal = weekDays
    .filter(d => d.workout && !d.isRestDay)
    .reduce((sum, d) => sum + (d.workout?.miles || 0), 0);

  return {
    completed: completedWorkouts,
    total: totalWorkouts,
    milesCompleted,
    milesTotal,
  };
}
