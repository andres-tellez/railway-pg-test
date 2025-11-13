/**
 * Week Timeline Utility Functions
 * Optimized helper functions for week timeline data processing
 */

import { startOfWeek, endOfWeek, eachDayOfInterval, parseISO, isToday as isTodayDate, format } from 'date-fns';

export interface Workout {
  date: string;
  workout_type: string;
  miles: number;
  description?: string;
  target_zone?: string;
  target_hr?: string;
  segments?: any;
}

export interface Activity {
  activity_id: number;
  date: string;
  distance_miles: number;
  name: string;
  type: string;
}

export interface WeekDay {
  date: Date;
  dateStr: string;
  workout?: Workout;
  activity?: Activity;
  isCompleted: boolean;
  isRestDay: boolean;
  isToday: boolean;
}

/**
 * Get this week's date range (Monday to Sunday)
 */
export function getThisWeekRange(): { weekStart: Date; weekEnd: Date } {
  const today = new Date();
  const weekStart = startOfWeek(today, { weekStartsOn: 1 }); // Monday
  const weekEnd = endOfWeek(today, { weekStartsOn: 1 }); // Sunday

  // Debug: Log week range
  console.log('[Week Range] Today:', format(today, 'yyyy-MM-dd'), 'Week Start:', format(weekStart, 'yyyy-MM-dd'), 'Week End:', format(weekEnd, 'yyyy-MM-dd'));

  return { weekStart, weekEnd };
}

/**
 * Match activity to workout (within 1 day, ±30% distance tolerance)
 */
export function matchActivityToWorkout(
  activity: Activity,
  workout: Workout
): boolean {
  // Extract date strings (YYYY-MM-DD format) - compare strings directly to avoid timezone issues
  const activityDateStr = activity.date.split('T')[0]; // Get date part only
  const workoutDateStr = workout.date.split('T')[0]; // Get date part only

  // Parse dates as local dates (not UTC) by creating Date objects directly
  // This avoids parseISO which interprets date-only strings as UTC
  const [activityYear, activityMonth, activityDay] = activityDateStr.split('-').map(Number);
  const [workoutYear, workoutMonth, workoutDay] = workoutDateStr.split('-').map(Number);

  const activityDateLocal = new Date(activityYear, activityMonth - 1, activityDay);
  const workoutDateLocal = new Date(workoutYear, workoutMonth - 1, workoutDay);

  const daysDiff = Math.abs(
    (activityDateLocal.getTime() - workoutDateLocal.getTime()) / (1000 * 60 * 60 * 24)
  );

  if (daysDiff > 1) return false;

  const distanceDiff = Math.abs(activity.distance_miles - workout.miles) / workout.miles;
  return distanceDiff <= 0.3;
}

/**
 * Normalize a date string to YYYY-MM-DD format, handling both date-only and datetime strings
 */
function normalizeDateString(dateStr: string): string {
  // Handle both "YYYY-MM-DD" and "YYYY-MM-DDTHH:MM:SS" formats
  return dateStr.split('T')[0];
}

/**
 * Process week data: create week days with matched activities
 */
export function processWeekData(
  workouts: Workout[],
  activities: Activity[],
  weekStart: Date,
  weekEnd: Date
): WeekDay[] {
  const days = eachDayOfInterval({ start: weekStart, end: weekEnd });

  return days.map((date) => {
    // Use format instead of toISOString to avoid UTC conversion issues
    // format() uses local time, so dates stay on the correct day
    const dateStr = format(date, 'yyyy-MM-dd');
    // Normalize workout dates to ensure consistent comparison
    // Debug: Log first few matches to verify date comparison
    const workout = workouts.find((w) => {
      const normalizedWorkoutDate = normalizeDateString(w.date);
      const matches = normalizedWorkoutDate === dateStr;
      if (matches && date.getDate() <= 15) { // Only log first few days
        console.log(`[Date Match] Day: ${dateStr}, Workout date: ${w.date} (normalized: ${normalizedWorkoutDate}), Match: ${matches}`);
      }
      return matches;
    });

    // Try to match activity to workout
    const activity = workout
      ? activities.find((act) => matchActivityToWorkout(act, workout))
      : undefined;

    const isCompleted = !!activity;
    const isRestDay = !workout || workout.workout_type?.toLowerCase().includes('rest');
    const isToday = isTodayDate(date);

    return {
      date,
      dateStr,
      workout,
      activity,
      isCompleted,
      isRestDay,
      isToday,
    };
  });
}

/**
 * Calculate weekly progress
 */
export function calculateWeeklyProgress(weekDays: WeekDay[]): {
  completed: number;
  total: number;
  milesCompleted: number;
  milesTotal: number;
} {
  const completedWorkouts = weekDays.filter((d) => d.isCompleted && !d.isRestDay).length;
  const totalWorkouts = weekDays.filter((d) => !d.isRestDay && d.workout).length;

  const milesCompleted = weekDays
    .filter((d) => d.isCompleted && d.activity)
    .reduce((sum, d) => sum + (d.activity?.distance_miles || 0), 0);

  const milesTotal = weekDays
    .filter((d) => d.workout && !d.isRestDay)
    .reduce((sum, d) => sum + (d.workout?.miles || 0), 0);

  return {
    completed: completedWorkouts,
    total: totalWorkouts,
    milesCompleted,
    milesTotal,
  };
}
