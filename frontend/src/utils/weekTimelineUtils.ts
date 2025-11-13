/**
 * Week Timeline Utility Functions
 * Simplified version using centralized date utilities
 */

import { format } from 'date-fns';
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
  date: string; // Will be normalized to YYYY-MM-DD
  distance_miles: number;
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
 * Normalize activity date to YYYY-MM-DD
 */
function normalizeActivity(activity: Activity): Activity {
  return {
    ...activity,
    date: toDateString(activity.date),
  };
}

/**
 * Match activity to workout (same day, ±30% distance)
 */
export function matchActivityToWorkout(activity: Activity, workout: Workout): boolean {
  const activityDate = toDateString(activity.date);
  const workoutDate = toDateString(workout.date);
  
  // Same day check (string comparison)
  if (activityDate !== workoutDate) {
    // Allow ±1 day tolerance
    const daysDiff = Math.abs(compareDates(activityDate, workoutDate));
    if (daysDiff > 1) return false;
  }
  
  // Distance check
  const distanceDiff = Math.abs(activity.distance_miles - workout.miles) / workout.miles;
  return distanceDiff <= 0.3;
}

/**
 * Process week data - SIMPLE version using string comparisons
 */
export function processWeekData(
  workouts: Workout[],
  activities: Activity[],
  weekStart: string, // YYYY-MM-DD
  weekEnd: string    // YYYY-MM-DD
): WeekDay[] {
  // Normalize all activities to date-only strings
  const normalizedActivities = activities.map(normalizeActivity);
  
  // Normalize all workouts to date-only strings
  const normalizedWorkouts = workouts.map(w => ({
    ...w,
    date: toDateString(w.date),
  }));
  
  // Generate week days
  const weekDays = getWeekDateStrings(weekStart);
  
  return weekDays.map(dateStr => {
    // Find workout for this day (simple string match)
    const workout = normalizedWorkouts.find(w => w.date === dateStr);
    
    // Find matching activity
    const activity = workout
      ? normalizedActivities.find(act => matchActivityToWorkout(act, workout))
      : undefined;
    
    // Create Date object only for display/formatting
    const date = dateStringToDate(dateStr);
    
    return {
      dateStr,
      date, // For display only
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
