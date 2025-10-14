/**
 * Shared helper functions for chart components
 * These functions provide common chart logic that can be reused across components
 */

import { CHART_SHADOWS } from './chartUtils';

// ============================================================================
// SHADOW HELPER FUNCTIONS
// ============================================================================

/**
 * Get bar shadow based on bar state and conditions
 * Handles special cases like no red shadow for current week
 *
 * @param barColor - The color type of the bar (normal, personal_record, significant_drop)
 * @param index - The index of the bar (0 = current week)
 * @param options - Optional configuration object
 * @param options.noRedForCurrentWeek - Whether to exclude red shadow for current week (default: true)
 * @param options.exceededGoal - Whether the bar exceeded its goal (for green shadow)
 * @returns CSS box-shadow string
 */
export const getBarShadow = (
  barColor: string,
  index: number,
  options: {
    noRedForCurrentWeek?: boolean;
    exceededGoal?: boolean;
  } = {}
): string => {
  const { noRedForCurrentWeek = true, exceededGoal = false } = options;

  // Special case: no red shadow for current week (index 0)
  if (barColor === 'significant_drop' && index !== 0 && !noRedForCurrentWeek) {
    return CHART_SHADOWS.RED;
  }

  // Green shadow for exceeded goals or personal records
  if (exceededGoal || barColor === 'personal_record') {
    return CHART_SHADOWS.GREEN;
  }

  // Default blue shadow
  return CHART_SHADOWS.BLUE;
};

// ============================================================================
// CHART CALCULATION HELPERS
// ============================================================================

/**
 * Calculate bar height in pixels based on value and maximum
 *
 * @param value - The actual value to represent
 * @param maxValue - The maximum value for scaling
 * @param maxHeight - The maximum height in pixels (default: 140)
 * @returns Height in pixels
 */
export const calculateBarHeight = (
  value: number,
  maxValue: number,
  maxHeight: number = 120
): number => {
  if (maxValue <= 0) return 40; // Minimum height
  const heightPercentage = value / maxValue;
  return Math.max(heightPercentage * maxHeight + 40, 40);
};

/**
 * Calculate chart maximum considering both actual and planned values
 *
 * @param actualValues - Array of actual values
 * @param plannedValues - Array of planned values (optional)
 * @param minimum - Minimum value to ensure (default: 1)
 * @returns Maximum value for chart scaling
 */
export const calculateChartMaximum = (
  actualValues: number[],
  plannedValues: number[] = [],
  minimum: number = 1
): number => {
  const allValues = [...actualValues, ...plannedValues];
  return Math.max(...allValues, minimum);
};

// ============================================================================
// DATA FORMATTING HELPERS
// ============================================================================

/**
 * Format distance values with consistent decimal places
 *
 * @param distance - The distance value to format
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted distance string
 */
export const formatDistance = (distance: number, decimals: number = 1): string => {
  return distance.toFixed(decimals);
};

/**
 * Format percentage values with consistent decimal places
 *
 * @param percentage - The percentage value to format
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted percentage string with % sign
 */
export const formatPercentage = (percentage: number, decimals: number = 1): string => {
  const sign = percentage >= 0 ? '+' : '';
  return `${sign}${percentage.toFixed(decimals)}%`;
};

// ============================================================================
// DATE FORMATTING HELPERS
// ============================================================================

/**
 * Format date string to MM/DD format
 *
 * @param dateString - ISO date string or date-like string
 * @returns Formatted date string (MM/DD)
 */
export const formatDate = (dateString: string): string => {
  try {
    const date = new Date(dateString);
    const month = date.getMonth() + 1; // getMonth() is 0-indexed
    const day = date.getDate();
    return `${month}/${day}`;
  } catch (error) {
    return dateString; // fallback to original string if parsing fails
  }
};

/**
 * Format week string for display
 *
 * @param weekString - Week string (typically YYYY-MM-DD format)
 * @returns Formatted week string (e.g., "Wk of 10/6")
 */
export const formatWeekString = (weekString: string): string => {
  try {
    const dateStr = weekString;
    const date = new Date(dateStr);
    const month = date.toLocaleDateString('en-US', { month: 'short' });
    const day = date.getDate();
    const year = date.getFullYear();
    return `Wk of ${month} ${day}, ${year}`;
  } catch (error) {
    return weekString; // fallback to original string
  }
};

// ============================================================================
// TREND HELPERS
// ============================================================================

/**
 * Get trend icon based on trend direction
 *
 * @param trend - Trend direction ('improving', 'declining', 'stable')
 * @returns Trend icon string
 */
export const getTrendIcon = (trend: string): string => {
  switch (trend) {
    case 'improving':
      return '↑';
    case 'declining':
      return '↓';
    default:
      return '→';
  }
};

/**
 * Determine if a change percentage represents a significant drop
 *
 * @param changePct - The percentage change
 * @param threshold - The threshold for significant drop (default: 40%)
 * @returns True if this is a significant drop
 */
export const isSignificantDrop = (changePct: number, threshold: number = 40): boolean => {
  return changePct <= -threshold;
};

// ============================================================================
// NUMBER FORMATTING HELPERS
// ============================================================================

/**
 * Format numbers with consistent decimal places for chart display
 *
 * @param value - The number to format
 * @param type - The type of value being formatted
 * @returns Formatted number string
 */
export const formatChartNumber = (value: number, type: 'distance' | 'vo2' | 'percentage' | 'score' | 'zone'): string => {
  switch (type) {
    case 'distance':
      return value.toFixed(1); // 1 decimal for distances (e.g., "5.0")
    case 'vo2':
      return value.toFixed(0); // No decimals for VO2 (e.g., "45")
    case 'percentage':
      return value.toFixed(1); // 1 decimal for percentages (e.g., "85.5")
    case 'score':
      return value.toFixed(0); // No decimals for scores (e.g., "8")
    case 'zone':
      return value.toFixed(1); // 1 decimal for heart rate zones (e.g., "12.5")
    default:
      return value.toFixed(1);
  }
};

/**
 * Create a formatted HR zone display string
 *
 * @param zoneNumber - The zone number (1-5)
 * @param percentage - The percentage value
 * @returns Formatted zone string (e.g., "Z1: 12.5%")
 */
export const formatHRZone = (zoneNumber: number, percentage: number): string => {
  return `Z${zoneNumber}: ${formatChartNumber(percentage, 'zone')}%`;
};

/**
 * Format change percentage with sign
 *
 * @param changePct - The percentage change
 * @returns Formatted change string (e.g., "+5.2%" or "-12.1%")
 */
export const formatChangePercentage = (changePct: number): string => {
  const sign = changePct >= 0 ? '+' : '';
  return `${sign}${formatChartNumber(changePct, 'percentage')}%`;
};

// ============================================================================
// CHART CONTAINER CALCULATIONS
// ============================================================================

/**
 * Calculate the total height needed for a chart container
 * This includes the tallest bar height plus padding for number display
 *
 * @param data - Array of chart data items
 * @param heightCalculator - Function to calculate height for each data item
 * @param numberPaddingTop - Extra padding above tallest bar (default: 80px)
 * @returns Total height in pixels needed for the chart container
 */
export const calculateChartContainerHeight = (data: any[], heightCalculator: (item: any) => number, numberPaddingTop: number = 80): number => {
  // Calculate the actual tallest bar height in pixels
  const tallestBarHeight = data.reduce((max, item) => {
    const heightPixels = heightCalculator(item);
    return Math.max(max, heightPixels);
  }, 0);

  // Add more padding above the tallest bar so numbers appear well within background
  return tallestBarHeight + numberPaddingTop;
};
