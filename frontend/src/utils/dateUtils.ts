/**
 * Simple Date Utilities
 *
 * RULE: All dates are stored/comparison as YYYY-MM-DD strings
 *       Date objects are ONLY created for display/formatting
 */

/**
 * Extract date-only string (YYYY-MM-DD) from any date format
 * Handles: "2024-11-12", "2024-11-12T22:13:04", Date objects
 */
export function toDateString(date: string | Date): string {
  if (date instanceof Date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  // String: extract date part (handles both "YYYY-MM-DD" and "YYYY-MM-DDTHH:MM:SS")
  return date.split('T')[0];
}

/**
 * Create Date object from YYYY-MM-DD string (for display only)
 */
export function dateStringToDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day);
}

/**
 * Compare two dates (as strings) - returns days difference
 */
export function compareDates(date1: string, date2: string): number {
  const d1 = dateStringToDate(date1);
  const d2 = dateStringToDate(date2);
  return Math.round((d1.getTime() - d2.getTime()) / (1000 * 60 * 60 * 24));
}

/**
 * Check if date string is today
 */
export function isToday(dateStr: string): boolean {
  const today = toDateString(new Date());
  return dateStr === today;
}

/**
 * Get this week's date range (Monday to Sunday) as date strings
 */
export function getThisWeekRange(): { weekStart: string; weekEnd: string } {
  const today = new Date();
  const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday, etc.
  const daysFromMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Convert to Monday = 0

  const monday = new Date(today);
  monday.setDate(today.getDate() - daysFromMonday);
  monday.setHours(0, 0, 0, 0);

  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  sunday.setHours(23, 59, 59, 999);

  return {
    weekStart: toDateString(monday),
    weekEnd: toDateString(sunday),
  };
}

/**
 * Generate array of date strings for a week (Monday to Sunday)
 */
export function getWeekDateStrings(weekStart: string): string[] {
  const start = dateStringToDate(weekStart);
  const dates: string[] = [];

  for (let i = 0; i < 7; i++) {
    const date = new Date(start);
    date.setDate(start.getDate() + i);
    dates.push(toDateString(date));
  }

  return dates;
}

/**
 * Get week range for a specific week start date
 */
export function getWeekRange(weekStart: string): { weekStart: string; weekEnd: string } {
  const start = dateStringToDate(weekStart);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);

  return {
    weekStart: toDateString(start),
    weekEnd: toDateString(end),
  };
}

/**
 * Get previous week's start date (Monday)
 */
export function getPreviousWeek(weekStart: string): string {
  const start = dateStringToDate(weekStart);
  const prevMonday = new Date(start);
  prevMonday.setDate(start.getDate() - 7);
  return toDateString(prevMonday);
}

/**
 * Get next week's start date (Monday)
 */
export function getNextWeek(weekStart: string): string {
  const start = dateStringToDate(weekStart);
  const nextMonday = new Date(start);
  nextMonday.setDate(start.getDate() + 7);
  return toDateString(nextMonday);
}

/**
 * Check if it's Sunday evening (after 4:30 PM Central / 10:30 PM UTC)
 * This is when the weekly rebuild process runs
 */
export function isSundayEvening(): boolean {
  const now = new Date();
  const dayOfWeek = now.getDay(); // 0 = Sunday
  const hour = now.getHours();
  const minute = now.getMinutes();

  // Check if it's Sunday and after 4:30 PM Central (22:30 UTC)
  // For simplicity, we'll check if it's Sunday and after 4:30 PM local time
  // In production, you might want to use a timezone library
  if (dayOfWeek === 0) {
    // Sunday - check if after 4:30 PM
    return hour > 16 || (hour === 16 && minute >= 30);
  }

  return false;
}

/**
 * Check if a week is in the future (next week or later)
 */
export function isFutureWeek(weekStart: string): boolean {
  const { weekStart: thisWeekStart } = getThisWeekRange();
  return compareDates(weekStart, thisWeekStart) > 0;
}

/**
 * Check if a week is in the past (previous week or earlier)
 */
export function isPastWeek(weekStart: string): boolean {
  const { weekStart: thisWeekStart } = getThisWeekRange();
  return compareDates(weekStart, thisWeekStart) < 0;
}
