/**
 * Shared React hooks for memoized chart styles
 * These hooks prevent unnecessary re-renders by memoizing static style objects
 */

import { useMemo } from 'react';
import { CHART_TRANSITIONS, CHART_BASE_CLASSES, CHART_NUMBER_FORMATTING } from '../utils/chartUtils';

// ============================================================================
// STATIC STYLE HOOKS
// ============================================================================

/**
 * Hook that returns a memoized static bar style object
 * Prevents recreation of the transition property on every render
 *
 * @returns Memoized style object with transition property
 */
export const useStaticBarStyle = () => {
  return useMemo(() => ({
    transition: CHART_TRANSITIONS.BAR
  }), []);
};

/**
 * Hook that returns memoized base CSS classes for chart bars
 * Prevents recreation of CSS class strings on every render
 *
 * @returns Memoized CSS class string
 */
export const useBarBaseClasses = () => {
  return useMemo(() => CHART_BASE_CLASSES.BAR, []);
};

/**
 * Hook that returns memoized current week ring classes
 * Prevents recreation of ring styling on every render
 *
 * @returns Memoized ring CSS class string
 */
export const useCurrentWeekRingClasses = () => {
  return useMemo(() => `${CHART_BASE_CLASSES.CURRENT_WEEK_RING} ${CHART_BASE_CLASSES.CURRENT_WEEK_RING_COLOR}`, []);
};

// ============================================================================
// DYNAMIC STYLE HOOKS
// ============================================================================

/**
 * Helper function that returns bar color classes based on state
 * This is a regular function, not a hook, to avoid Rules of Hooks violations
 *
 * @param colorType - The type of color (normal, personal_record, significant_drop)
 * @param isCurrentWeek - Whether this is the current week
 * @returns CSS class string for the bar
 */
export const getBarColorClasses = (colorType: string, isCurrentWeek: boolean): string => {
  const baseClasses = CHART_BASE_CLASSES.BAR;
  const currentWeekRing = isCurrentWeek ? `${CHART_BASE_CLASSES.CURRENT_WEEK_RING} ${CHART_BASE_CLASSES.CURRENT_WEEK_RING_COLOR}` : '';

  // Current week is always grey
  if (isCurrentWeek) {
    return `${baseClasses} bg-gray-500 ${currentWeekRing}`;
  }

  // Other weeks use their respective colors
  switch (colorType) {
    case 'personal_record':
      return `${baseClasses} bg-green-500`;
    case 'significant_drop':
      return `${baseClasses} bg-red-500`;
    default:
      return `${baseClasses} bg-blue-500`;
  }
};

// ============================================================================
// NUMBER DISPLAY HELPERS
// ============================================================================

/**
 * Get CSS classes for numbers displayed above chart bars
 *
 * @param size - The size variant for the number display
 * @returns CSS class string for the number display
 */
export const getNumberDisplayClasses = (size: 'small' | 'medium' | 'large' = 'medium'): string => {
  switch (size) {
    case 'small':
      return CHART_NUMBER_FORMATTING.ABOVE_BAR_CLASSES.SMALL;
    case 'medium':
      return CHART_NUMBER_FORMATTING.ABOVE_BAR_CLASSES.MEDIUM;
    case 'large':
      return CHART_NUMBER_FORMATTING.ABOVE_BAR_CLASSES.LARGE;
    default:
      return CHART_NUMBER_FORMATTING.ABOVE_BAR_CLASSES.MEDIUM;
  }
};

// ============================================================================
// CHART CONTAINER STYLES
// ============================================================================

import { CHART_LAYOUT, CHART_BACKGROUNDS } from '../utils/chartUtils';

/**
 * Generate complete chart container style object
 *
 * @param height - Total height in pixels for the container
 * @param backgroundType - Background gradient type ('light', 'medium', 'dark')
 * @returns Complete style object for chart container
 */
export const getChartContainerStyle = (height: number, backgroundType: 'light' | 'medium' | 'dark' = CHART_LAYOUT.DEFAULT_BACKGROUND) => {
  return {
    height: `${height}px`,
    display: 'flex',
    alignItems: 'flex-end',
    gap: CHART_LAYOUT.GAP,
    padding: CHART_LAYOUT.PADDING,
    borderRadius: '0.75rem',
    background: CHART_BACKGROUNDS[backgroundType.toUpperCase() as keyof typeof CHART_BACKGROUNDS]
  };
};
