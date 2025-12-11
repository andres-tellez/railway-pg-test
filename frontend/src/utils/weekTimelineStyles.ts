/**
 * Week Timeline Style Constants
 * Centralized styling configuration for HomeScreen week timeline
 */

export const WEEK_TIMELINE_STYLES = {
  // Container
  container: "bg-white rounded-lg shadow-sm overflow-hidden",
  containerPadding: "p-3 sm:p-4 md:p-6",

  // Title
  title: "text-lg sm:text-xl md:text-2xl font-semibold text-gray-900 mb-3 sm:mb-4",

  // Day grid
  dayGrid: "grid grid-cols-7 gap-1 sm:gap-2 md:gap-3 mb-4",

  // Day button base
  dayButtonBase: "p-1.5 sm:p-2 md:p-3 rounded-lg border-2 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 sm:focus:ring-offset-2 min-w-0 flex flex-col items-center justify-center relative min-h-[44px] min-w-[44px] sm:min-h-[48px] sm:min-w-[48px]",

  // Day button states
  dayButtonDefault: "border-blue-300 hover:border-blue-400 bg-blue-50",
  dayButtonSelected: "border-blue-600 bg-blue-600",
  dayButtonCompleted: "border-blue-300 bg-blue-50",
  dayButtonRest: "bg-gray-200 border-gray-300",

  // Day content
  dayName: "text-xs sm:text-sm font-medium text-gray-700 mb-0.5 sm:mb-1 leading-tight",
  dayNameSelected: "text-xs sm:text-sm font-medium text-white mb-0.5 sm:mb-1 leading-tight",
  dayNameRest: "text-xs sm:text-sm font-medium text-gray-500 mb-0.5 sm:mb-1 leading-tight",
  dayNumber: "text-sm sm:text-base md:text-lg font-semibold mb-0.5 sm:mb-1 leading-tight",
  dayNumberSelected: "text-sm sm:text-base md:text-lg font-semibold text-white mb-0.5 sm:mb-1 leading-tight",
  dayNumberCompleted: "text-gray-900",
  dayNumberRest: "text-gray-500",
  dayNumberDefault: "text-gray-900",

  // Day indicators
  indicatorCompleted: "absolute top-0 right-1 sm:right-1.5 text-green-600 text-xl sm:text-2xl md:text-3xl font-bold z-10 pointer-events-none leading-none transform translate-y-[-100%]",
  indicatorRest: "text-gray-400 text-xs opacity-60",

  // Day workout info
  workoutInfo: "text-xs text-gray-600 mt-1",
  workoutInfoRest: "text-xs text-gray-400 mt-1",

  // Progress section
  progressSection: "border-b border-gray-200 pb-4 mb-4",
  progressHeader: "flex justify-between items-center mb-2",
  progressLabel: "text-sm text-gray-600",
  progressValue: "text-sm font-semibold text-gray-900",
  progressBarContainer: "w-full bg-gray-200 rounded-full h-2 mb-2",
  progressBarFill: "bg-green-600 h-2 rounded-full transition-all duration-300",
  progressMiles: "text-sm text-gray-600",

  // Details panel
  detailsPanel: "bg-white border-l-2 border-blue-600 rounded-lg shadow-sm p-3 sm:p-4 md:p-6",
  detailsTitle: "text-2xl font-semibold text-gray-900 mb-4",
  detailsSubtitle: "text-lg font-medium text-gray-900",
  detailsText: "text-base text-gray-600",
  detailsSection: "space-y-2 mb-4",
  detailsDivider: "mt-4 pt-4 border-t border-gray-200",

  // Workout structure cards
  workoutStructureHeader: "text-sm font-semibold text-gray-700 mb-3",
  workoutStructureCards: "space-y-2",
  workoutStructureCard: "bg-gray-50 border border-gray-200 rounded-lg p-3 hover:bg-gray-100 transition-colors",
  workoutStructureCardName: "text-sm font-semibold text-gray-900 mb-1",
  workoutStructureCardDetails: "text-sm text-gray-600 flex flex-wrap items-center gap-2",
  workoutStructureCardDetailItem: "flex items-center gap-1",

  // Status colors
  statusCompleted: "text-green-700 font-semibold",
  statusUpcoming: "text-gray-700",

  // Links
  link: "text-blue-600 hover:underline text-sm",

  // Comparison grid
  comparisonGrid: "grid grid-cols-2 gap-2 sm:gap-4 mb-4",
  comparisonColumn: "border border-gray-200 rounded-lg p-2 sm:p-3",
  comparisonHeader: "text-sm font-semibold text-gray-600 mb-2 uppercase tracking-wide",
  comparisonValue: "text-lg font-medium text-gray-900",
  comparisonSubValue: "text-sm text-gray-600 mt-1",

  // Coach's note
  coachNoteSection: "bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4",
  coachNoteHeader: "flex items-center mb-3",
  coachNoteIcon: "text-xl mr-2",
  coachNoteTitle: "text-base font-semibold text-gray-900",
  coachNoteText: "text-sm text-gray-700 mb-3",
  coachNoteLink: "text-sm text-blue-600 hover:underline",

  // Empty state / Activity summary
  emptyStateSection: "bg-white rounded-lg shadow-sm p-6 md:p-8",
  emptyStateIcon: "text-4xl mb-3",
  emptyStateTitle: "text-xl font-semibold text-gray-900 mb-4",
  emptyStateText: "text-gray-600 mb-4",
  emptyStateButton: "inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors shadow-lg hover:shadow-xl",

  // Activity summary
  activitySummarySection: "space-y-4",
  activitySummaryRow: "flex justify-between items-center py-2 border-b border-gray-100 last:border-0",
  activitySummaryLabel: "text-sm text-gray-600",
  activitySummaryValue: "text-sm font-semibold text-gray-900",
  activitySummaryStats: "grid grid-cols-2 gap-4 mb-4",
  activitySummaryStat: "bg-gray-50 rounded-lg p-3",
  activitySummaryStatLabel: "text-xs text-gray-600 mb-1",
  activitySummaryStatValue: "text-lg font-semibold text-gray-900",
  activitySummaryLinks: "flex flex-wrap gap-3 mt-4 pt-4 border-t border-gray-200",
  activitySummaryLink: "text-sm text-blue-600 hover:underline",
  recentActivityItem: "bg-gray-50 rounded-lg p-3 mb-2",
  recentActivityName: "text-sm font-medium text-gray-900 mb-1",
  recentActivityDetails: "text-xs text-gray-600",

  // ============================================================================
  // STANDARDIZED TYPOGRAPHY FOR HOME PAGE
  // ============================================================================

  // Workout Type Title
  workoutTypeTitle: "text-2xl font-bold text-gray-900 mb-1",
  workoutTypeSubtitle: "text-sm font-normal text-gray-600 mb-4",

  // Card Headers (Pace, Heart Rate, Distance)
  cardHeader: "text-base font-semibold text-gray-700",

  // Status Labels (Perfect, Close, Off Target)
  statusLabel: "text-sm font-semibold",
  statusIcon: "text-lg font-bold",

  // Actual Values (above range bar)
  actualValue: "text-base font-bold",

  // Range Labels (below bar ends)
  rangeLabel: "text-xs font-normal text-gray-600",

  // Distance Value
  distanceValue: "text-lg font-medium text-gray-900",

  // Card Container
  metricCard: "border border-gray-200 rounded-lg p-4 mb-4 bg-white",
} as const;

/**
 * Get day button classes based on state
 */
export function getDayButtonClasses(
  isSelected: boolean,
  isCompleted: boolean,
  isRestDay: boolean,
  isToday?: boolean
): string {
  const base = WEEK_TIMELINE_STYLES.dayButtonBase;

  if (isSelected) {
    return `${base} ${WEEK_TIMELINE_STYLES.dayButtonSelected}`;
  }
  if (isCompleted && !isRestDay) {
    return `${base} ${WEEK_TIMELINE_STYLES.dayButtonCompleted}`;
  }
  if (isRestDay) {
    return `${base} ${WEEK_TIMELINE_STYLES.dayButtonRest}`;
  }
  // Add subtle highlight for today if not selected
  if (isToday && !isSelected) {
    return `${base} ${WEEK_TIMELINE_STYLES.dayButtonDefault} ring-2 ring-blue-400 ring-offset-1`;
  }
  return `${base} ${WEEK_TIMELINE_STYLES.dayButtonDefault}`;
}

/**
 * Get day number classes based on state
 */
export function getDayNumberClasses(
  isCompleted: boolean,
  isRestDay: boolean,
  isSelected?: boolean
): string {
  const base = WEEK_TIMELINE_STYLES.dayNumber;

  if (isSelected) {
    return WEEK_TIMELINE_STYLES.dayNumberSelected;
  }
  if (isCompleted && !isRestDay) {
    return `${base} ${WEEK_TIMELINE_STYLES.dayNumberCompleted}`;
  }
  if (isRestDay) {
    return `${base} ${WEEK_TIMELINE_STYLES.dayNumberRest}`;
  }
  return `${base} ${WEEK_TIMELINE_STYLES.dayNumberDefault}`;
}

/**
 * Get day name classes based on state
 */
export function getDayNameClasses(isRestDay: boolean, isSelected?: boolean): string {
  if (isSelected) {
    return WEEK_TIMELINE_STYLES.dayNameSelected;
  }
  if (isRestDay) {
    return WEEK_TIMELINE_STYLES.dayNameRest;
  }
  return WEEK_TIMELINE_STYLES.dayName;
}
