/**
 * GYR Metric Card Utilities
 * Centralized styling and configuration for GYR metric cards
 */

// ============================================================================
// CARD TEMPLATE CONFIGURATION
// ============================================================================

export const GYR_CARD_TEMPLATE = {
  // Layout containers
  card: "bg-white rounded-lg shadow-lg border border-gray-100 flex flex-col",
  header: "px-6 pt-6 pb-2",
  timeline: "flex-1 flex items-center justify-center px-6",
  legend: "mt-4 mx-0",

  // Typography
  title: "text-xl font-bold text-gray-900",

  // Timeline elements
  timelineBars: "flex items-center justify-center gap-3",
  bar: "rounded-sm transition-all duration-200 hover:opacity-80 hover:scale-105 hover:shadow-md cursor-pointer",
  barSize: { width: '24px', height: '64px' },

  // Legend elements
  divider: "h-px bg-gradient-to-r from-transparent via-gray-200 to-transparent mb-3",
  legendContainer: "bg-gray-800 rounded-b-lg px-3 pt-3 pb-3 flex gap-3",
  legendItem: "flex items-center gap-2",
  legendSquare: "w-5 h-5 rounded shadow-sm",
  legendText: "text-xs text-white leading-tight"
} as const;

// ============================================================================
// CARD SIZE VARIANTS
// ============================================================================

export const GYR_CARD_SIZES = {
  compact: "w-80 min-h-56",
  default: "w-96 min-h-64",
  large: "w-[28rem] min-h-72"
} as const;

// ============================================================================
// STATUS COLOR UTILITIES
// ============================================================================

export const GYR_STATUS_COLORS = {
  green: 'bg-emerald-400',
  yellow: 'bg-amber-400',
  red: 'bg-red-400',
  gray: 'bg-gray-200'
} as const;

/**
 * Get the appropriate color class for a GYR status
 */
export const getStatusColor = (status: 'green' | 'yellow' | 'red' | 'gray'): string => {
  return GYR_STATUS_COLORS[status] || GYR_STATUS_COLORS.gray;
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Generate tooltip text for a timeline bar
 */
export const generateBarTooltip = (score: { value: number; date: string; status: string }, index: number): string => {
  return `Week ${index + 1}: ${score.date} - ${score.value}% (${score.status})`;
};

/**
 * Get the combined card classes with size variant
 */
export const getCardClasses = (size: keyof typeof GYR_CARD_SIZES = 'default'): string => {
  return `${GYR_CARD_TEMPLATE.card} ${GYR_CARD_SIZES[size]}`;
};

/**
 * Get the combined bar classes with status color
 */
export const getBarClasses = (status: 'green' | 'yellow' | 'red' | 'gray'): string => {
  return `${GYR_CARD_TEMPLATE.bar} ${getStatusColor(status)}`;
};

/**
 * Get the combined legend square classes with status color
 */
export const getLegendSquareClasses = (status: 'green' | 'yellow' | 'red'): string => {
  return `${GYR_CARD_TEMPLATE.legendSquare} ${getStatusColor(status)}`;
};

/**
 * Get the bar size styles object
 */
export const getBarStyles = (): React.CSSProperties => {
  return GYR_CARD_TEMPLATE.barSize;
};
