/**
 * Shared chart constants and styles used across all chart components
 * This ensures consistency and provides a single source of truth for chart styling
 */

// ============================================================================
// CHART TRANSITIONS
// ============================================================================

export const CHART_TRANSITIONS = {
  /** Standard bar transition animation */
  BAR: 'all 0.075s cubic-bezier(0.4, 0, 0.2, 1)',
  /** Hover transition for interactive elements */
  HOVER: 'transition-all duration-75'
} as const;

// ============================================================================
// CHART SHADOWS
// ============================================================================

export const CHART_SHADOWS = {
  /** Red shadow for significant drops/negative indicators */
  RED: '0 2px 8px rgba(239, 68, 68, 0.3)',
  /** Green shadow for positive indicators (personal records, exceeded goals) */
  GREEN: '0 2px 8px rgba(34, 197, 94, 0.3)',
  /** Blue shadow for default/normal state */
  BLUE: '0 2px 8px rgba(59, 130, 246, 0.2)',
  /** Dark shadow for overlays and goal indicators */
  DARK: '0 1px 2px rgba(0,0,0,0.1)'
} as const;

// ============================================================================
// CHART BASE CSS CLASSES
// ============================================================================

export const CHART_BASE_CLASSES = {
  /** Base classes for all chart bars */
  BAR: 'w-full rounded-t-lg transition-all duration-75 cursor-pointer relative hover:scale-105 hover:shadow-lg',
  /** Base classes for bar containers (individual bar wrapper) */
  BAR_CONTAINER: 'flex flex-col items-center justify-end flex-1 min-w-0',
  /** Base classes for tooltip containers */
  TOOLTIP_CONTAINER: 'flex flex-col items-center',
  /** Ring effect for current week highlighting */
  CURRENT_WEEK_RING: 'ring-2 ring-opacity-50',
  /** Ring colors for current week */
  CURRENT_WEEK_RING_COLOR: 'ring-gray-200'
} as const;

// ============================================================================
// CHART COLORS
// ============================================================================

export const CHART_COLORS = {
  /** Background colors for different bar states */
  BACKGROUND: {
    NORMAL: 'bg-blue-500',
    PERSONAL_RECORD: 'bg-green-500',
    SIGNIFICANT_DROP: 'bg-red-500',
    CURRENT_WEEK: 'bg-gray-500'
  },
  /** Text colors for different states */
  TEXT: {
    PRIMARY: 'text-gray-700',
    WHITE: 'text-white',
    GRAY: 'text-gray-400'
  }
} as const;

// ============================================================================
// CHART OVERLAY STYLES
// ============================================================================

export const CHART_OVERLAYS = {
  /** Dark overlay for planned/goal indicators */
  DARK_OVERLAY: 'rgba(0, 0, 0, 0.25)',
  /** Gradient overlay styles */
  GRADIENT_OVERLAY: 'linear-gradient(to bottom, rgba(0,0,0,0.8), rgba(0,0,0,0.4), rgba(0,0,0,0.25))'
} as const;

// ============================================================================
// CHART LAYOUT CONSTANTS
// ============================================================================

export const CHART_LAYOUT = {
  /** Standard chart height in pixels */
  MAX_HEIGHT_PX: 140,
  /** Standard bar border radius */
  BORDER_RADIUS: '0.5rem 0.5rem 0 0',
  /** Standard spacing */
  GAP: '0.25rem',
  /** Standard padding */
  PADDING: '1.5rem',
  /** Extra padding above tallest bar for number display */
  NUMBER_PADDING_TOP: 80,
  /** Default background type for all charts */
  DEFAULT_BACKGROUND: 'light'
} as const;

// ============================================================================
// CHART BACKGROUNDS
// ============================================================================

export const CHART_BACKGROUNDS = {
  /** Light gradient background (original default) */
  LIGHT: 'linear-gradient(to top, rgb(243 244 246), rgb(249 250 251))',
  /** Medium gradient background (darker than light) */
  MEDIUM: 'linear-gradient(to top, rgb(229 231 235), rgb(243 244 246))',
  /** Dark gradient background (darkest option) */
  DARK: 'linear-gradient(to top, rgb(209 213 219), rgb(229 231 235))'
} as const;

// ============================================================================
// CHART NUMBER FORMATTING
// ============================================================================

export const CHART_NUMBER_FORMATTING = {
  /** CSS classes for numbers above bars */
  ABOVE_BAR_CLASSES: {
    SMALL: 'text-xs font-semibold text-gray-700 mb-1',
    MEDIUM: 'text-sm font-semibold text-gray-700 mb-1',
    LARGE: 'text-sm font-semibold whitespace-nowrap text-gray-700'
  },
  /** CSS classes for numbers in tooltips */
  TOOLTIP_CLASSES: {
    PRIMARY: 'text-white font-semibold',
    SECONDARY: 'text-gray-300',
    PERCENTAGE: 'font-semibold'
  }
} as const;
