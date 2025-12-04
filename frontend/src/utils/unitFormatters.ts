/**
 * Unit Formatting Utilities
 *
 * Pure utility functions for converting and formatting units.
 * All functions are pure (no side effects) and can be tested in isolation.
 *
 * Input: Values in base units (miles, seconds per mile) from backend
 * Output: Formatted strings in user's preferred unit system
 *
 * === DISTANCE FORMATTING GUIDELINES ===
 *
 * Two functions exist because training plans must use human-friendly,
 * standardized distances, while other UI surfaces may require precision.
 *
 * 1. formatDistance()
 * -------------------
 * PURPOSE:
 *   - General-purpose formatting
 *   - Suitable for charts, metrics pages, and form fields
 *
 * OUTPUT:
 *   - Includes decimals (default 1 decimal place)
 *   - Includes unit label (e.g., "5.0 mi" or "8.0 km")
 *   - Good for precise numeric reporting
 *
 * USE THIS IN:
 *   - Charts (TotalMilesActualVsPlanChart, LongestRunsChart)
 *   - Tooltip numeric displays
 *   - Forms (NewPlanFormV2)
 *   - Metrics pages
 *   - Progress bars
 *
 *
 * 2. formatDistanceNumber()
 * -------------------------
 * PURPOSE:
 *   - Training-plan-specific smart rounding
 *   - UX-first rounded display
 *
 * OUTPUT:
 *   - Returns number string only (no unit label)
 *   - Whole km (metric)
 *   - Rounded-up miles for anything .5+ (imperial)
 *   - Race-specific logic for 26.2 / 13.1
 *
 * USE THIS IN:
 *   - PlanOverviewTable.tsx
 *   - PlanPage.tsx
 *   - MyPlan.tsx
 *   - WorkoutDetails.tsx (for plan workout data only)
 *   - Daily/weekly workout cards
 *   - Plan draft previews
 *
 * IMPORTANT:
 *   - formatDistanceNumber() returns ONLY the number (e.g., "5" or "8")
 *   - You must manually add the unit: `${formatDistanceNumber(miles, unitSystem)} ${unitSystem === 'metric' ? 'km' : 'mi'}`
 *
 * NEVER USE formatDistance() INSIDE A TRAINING PLAN.
 * NEVER USE formatDistanceNumber() INSIDE A CHART.
 */

export type UnitSystem = 'imperial' | 'metric';

// Conversion constants
const MI_TO_KM = 1.609344;
const KM_TO_MI = 1 / MI_TO_KM;
const SEC_PER_MI_TO_SEC_PER_KM = 1 / MI_TO_KM;

// ============================================================================
// DISTANCE CONVERSIONS
// ============================================================================

/**
 * Format distance for display (General-purpose)
 *
 * Use for: Charts, forms, metrics pages where decimals are acceptable
 *
 * @param miles - Distance in miles (from backend)
 * @param unitSystem - User's preferred unit system
 * @param precision - Number of decimal places (default: 1)
 * @returns Formatted string like "5.0 mi" or "8.0 km" (includes unit label)
 *
 * @example
 * formatDistance(5.0, 'imperial') // "5.0 mi"
 * formatDistance(5.0, 'metric')  // "8.0 km"
 */
export function formatDistance(
  miles: number,
  unitSystem: UnitSystem = 'imperial',
  precision: number = 1
): string {
  const value = unitSystem === 'metric' ? miles * MI_TO_KM : miles;
  const unit = unitSystem === 'metric' ? 'km' : 'mi';
  return `${value.toFixed(precision)} ${unit}`;
}

/**
 * Check if a km value matches a standard race distance
 * @internal - Helper function
 */
function isRaceDistance(km: number): boolean {
  const raceDistances = [42.2, 21.1, 10.0, 5.0];
  return raceDistances.some(race => Math.abs(km - race) < 0.1);
}

/**
 * Check if a miles value matches a standard race distance
 * @internal - Helper function
 */
function isRaceDistanceMiles(miles: number): boolean {
  const raceDistancesMiles = [26.2, 13.1, 6.21371, 3.10686]; // Marathon, Half, 10K, 5K
  return raceDistancesMiles.some(race => Math.abs(miles - race) < 0.1);
}

/**
 * Convert miles to display value with smart rounding
 * - Metric: whole km (except race distances and small intervals < 2 km)
 * - Imperial: 1 decimal place
 *
 * @param miles - Distance in miles
 * @param unitSystem - User's preferred unit system
 * @returns Distance in miles (imperial) or kilometers (metric)
 */
export function toDisplayDistance(miles: number, unitSystem: UnitSystem): number {
  if (unitSystem === 'metric') {
    const km = miles * MI_TO_KM;

    // Race distances: preserve exact value (42.2, 21.1, 10.0, 5.0)
    if (isRaceDistance(km)) {
      return Math.round(km * 10) / 10; // 1 decimal
    }

    // Small distances (< 2 km): likely intervals, allow decimals
    if (km < 2.0) {
      return Math.round(km * 10) / 10; // 1 decimal
    }

    // Everything else: round to whole km
    return Math.round(km);
  }

  // Imperial: 1 decimal place
  return Math.round(miles * 10) / 10;
}

/**
 * Format distance for training plans (Smart rounding)
 *
 * Use for: Plan tables, workout cards, user-facing plan displays
 *
 * Behavior:
 * - Metric: Whole km (no decimals), except race distances (1 decimal)
 * - Imperial: Round .5 up to whole miles, except race distances (1 decimal)
 * - Returns number string only (no unit label - you must add it)
 *
 * @param miles - Distance in miles (from backend)
 * @param unitSystem - User's preferred unit system
 * @returns Formatted number string (no unit label)
 *
 * @example
 * formatDistanceNumber(6.835, 'metric') // "11" (whole km)
 * formatDistanceNumber(26.2, 'metric') // "42.2" (race distance)
 * formatDistanceNumber(5.5, 'imperial') // "6" (rounded up from .5)
 * formatDistanceNumber(13.5, 'imperial') // "14" (rounded up from .5)
 * formatDistanceNumber(26.2, 'imperial') // "26.2" (race distance)
 *
 * Usage:
 * const formatted = formatDistanceNumber(miles, unitSystem);
 * const display = `${formatted} ${unitSystem === 'metric' ? 'km' : 'mi'}`;
 */
export function formatDistanceNumber(miles: number, unitSystem: UnitSystem): string {
  if (unitSystem === 'metric') {
    const km = miles * MI_TO_KM;
    const isRaceDist = isRaceDistance(km);

    // Race distances: keep 1 decimal (42.2, 21.1, 10.0, 5.0)
    if (isRaceDist) {
      return (Math.round(km * 10) / 10).toFixed(1);
    }

    // Everything else: whole number (no decimals)
    return Math.round(km).toFixed(0);
  }

  // Imperial
  const isRaceDist = isRaceDistanceMiles(miles);

  // Race distances: keep 1 decimal (26.2, 13.1, etc.)
  if (isRaceDist) {
    return miles.toFixed(1);
  }

  // For .5 values, round up to next whole number
  // Check if the value is exactly .5 (within floating point tolerance)
  const remainder = miles % 1;
  if (Math.abs(remainder - 0.5) < 0.01) {
    return Math.ceil(miles).toFixed(0); // 5.5 → 6, 13.5 → 14
  }

  // Whole numbers or other decimals: round normally
  return Math.round(miles).toFixed(0);
}

/**
 * Convert display distance back to miles (for API calls)
 *
 * @param displayValue - Distance in user's preferred unit
 * @param unitSystem - User's preferred unit system
 * @returns Distance in miles (for backend)
 */
export function fromDisplayDistance(displayValue: number, unitSystem: UnitSystem): number {
  if (unitSystem === 'metric') {
    return Math.round(displayValue * KM_TO_MI * 10) / 10;
  }
  return Math.round(displayValue * 10) / 10;
}

// ============================================================================
// PACE CONVERSIONS
// ============================================================================

/**
 * Format pace for display
 *
 * @param secondsPerMile - Pace in seconds per mile (from backend)
 * @param unitSystem - User's preferred unit system
 * @returns Formatted string like "9:45/mi" or "6:03/km"
 *
 * @example
 * formatPace(585, 'imperial') // "9:45/min/mi" (9:45 per mile)
 * formatPace(585, 'metric')   // "6:03/min/km" (~6:03 per km)
 */
export function formatPace(secondsPerMile: number, unitSystem: UnitSystem = 'imperial'): string {
  const secondsPerUnit = unitSystem === 'metric'
    ? secondsPerMile * SEC_PER_MI_TO_SEC_PER_KM
    : secondsPerMile;

  const minutes = Math.floor(secondsPerUnit / 60);
  const seconds = Math.floor(secondsPerUnit % 60);
  const unit = unitSystem === 'metric' ? 'min/km' : 'min/mi';

  return `${minutes}:${seconds.toString().padStart(2, '0')} ${unit}`;
}

/**
 * Format pace range for display
 *
 * @param minSecondsPerMile - Minimum pace in seconds per mile
 * @param maxSecondsPerMile - Maximum pace in seconds per mile
 * @param unitSystem - User's preferred unit system
 * @returns Formatted string like "9:30-10:00/min/mi" or "6:00-6:12/min/km"
 */
export function formatPaceRange(
  minSecondsPerMile: number,
  maxSecondsPerMile: number,
  unitSystem: UnitSystem = 'imperial'
): string {
  const minDisplay = unitSystem === 'metric'
    ? minSecondsPerMile * SEC_PER_MI_TO_SEC_PER_KM
    : minSecondsPerMile;
  const maxDisplay = unitSystem === 'metric'
    ? maxSecondsPerMile * SEC_PER_MI_TO_SEC_PER_KM
    : maxSecondsPerMile;

  const minMinutes = Math.floor(minDisplay / 60);
  const minSeconds = Math.floor(minDisplay % 60);
  const maxMinutes = Math.floor(maxDisplay / 60);
  const maxSeconds = Math.floor(maxDisplay % 60);

  const unit = unitSystem === 'metric' ? 'min/km' : 'min/mi';

  // If range is very small, show single pace
  if (Math.abs(minDisplay - maxDisplay) < 1.0) {
    return `${minMinutes}:${minSeconds.toString().padStart(2, '0')} ${unit}`;
  }

  return `${minMinutes}:${minSeconds.toString().padStart(2, '0')}-${maxMinutes}:${maxSeconds.toString().padStart(2, '0')} ${unit}`;
}

/**
 * Convert seconds per mile to seconds per display unit
 *
 * @param secondsPerMile - Pace in seconds per mile
 * @param unitSystem - User's preferred unit system
 * @returns Pace in seconds per mile (imperial) or seconds per km (metric)
 */
export function toDisplayPace(secondsPerMile: number, unitSystem: UnitSystem): number {
  if (unitSystem === 'metric') {
    return Math.round(secondsPerMile * SEC_PER_MI_TO_SEC_PER_KM * 10) / 10;
  }
  return Math.round(secondsPerMile * 10) / 10;
}

/**
 * Parse and convert pace string (e.g., "9:30-10:00/mi" or "9:30/mi")
 * to user's preferred unit system
 *
 * @param paceString - Pace string like "9:30-10:00/mi" or "9:30/mi"
 * @param unitSystem - User's preferred unit system
 * @returns Formatted string like "9:30-10:00/min/mi" or "5:54-6:13/min/km"
 *
 * @example
 * parseAndConvertPaceString("9:30-10:00/mi", "imperial") // "9:30-10:00/min/mi"
 * parseAndConvertPaceString("9:30-10:00/mi", "metric")   // "5:54-6:13/min/km"
 */
export function parseAndConvertPaceString(
  paceString: string,
  unitSystem: UnitSystem = 'imperial'
): string {
  if (!paceString) return '';

  // Handle range format: "9:23—9:53/mi" (backend uses em dash —) or "9:30-10:00/min/mi"
  // Backend format: "9:23—9:53/mi" (em dash, no /min/)
  // Also handles en dash (–) used in HeartRateZones.tsx
  const rangeMatch = paceString.match(/^(\d+:\d+)[-–—](\d+:\d+)\/(?:min\/)?(mi|km)$/);
  // Handle single format: "9:30/mi" or "9:30/min/mi"
  const singleMatch = paceString.match(/^(\d+:\d+)\/(?:min\/)?(mi|km)$/);

  if (rangeMatch) {
    // Range format - convert both paces
    const [, minPace, maxPace, originalUnit] = rangeMatch;
    const minSeconds = parsePaceStringToSeconds(minPace);
    const maxSeconds = parsePaceStringToSeconds(maxPace);

    // Convert from original unit to seconds per mile
    const minSecondsPerMile = originalUnit === 'mi'
      ? minSeconds
      : minSeconds / SEC_PER_MI_TO_SEC_PER_KM;
    const maxSecondsPerMile = originalUnit === 'mi'
      ? maxSeconds
      : maxSeconds / SEC_PER_MI_TO_SEC_PER_KM;

    // Format using formatPaceRange which handles conversion
    return formatPaceRange(minSecondsPerMile, maxSecondsPerMile, unitSystem);
  }

  if (singleMatch) {
    // Single pace format
    const [, pace, originalUnit] = singleMatch;
    const seconds = parsePaceStringToSeconds(pace);

    // Convert from original unit to seconds per mile
    const secondsPerMile = originalUnit === 'mi'
      ? seconds
      : seconds / SEC_PER_MI_TO_SEC_PER_KM;

    // Format using formatPace which handles conversion
    return formatPace(secondsPerMile, unitSystem);
  }

  // If format doesn't match, return as-is (fallback for edge cases)
  return paceString;
}

/**
 * Parse pace string (e.g., "9:30") to total seconds
 * @internal - Helper function
 */
function parsePaceStringToSeconds(paceStr: string): number {
  const [minutes, seconds] = paceStr.split(':').map(Number);
  return (minutes * 60) + (seconds || 0);
}

// ============================================================================
// ELEVATION CONVERSIONS
// ============================================================================

const FEET_TO_METER = 0.3048;
const METER_TO_FEET = 1 / FEET_TO_METER;

/**
 * Format elevation for display
 *
 * @param feet - Elevation in feet (from backend)
 * @param unitSystem - User's preferred unit system
 * @returns Formatted string like "500 ft" or "152 m"
 */
export function formatElevation(feet: number, unitSystem: UnitSystem = 'imperial'): string {
  if (unitSystem === 'metric') {
    const meters = Math.round(feet * FEET_TO_METER);
    return `${meters} m`;
  }
  return `${Math.round(feet)} ft`;
}

/**
 * Convert elevation to display value
 *
 * @param feet - Elevation in feet
 * @param unitSystem - User's preferred unit system
 * @returns Elevation in feet (imperial) or meters (metric)
 */
export function toDisplayElevation(feet: number, unitSystem: UnitSystem): number {
  if (unitSystem === 'metric') {
    return Math.round(feet * FEET_TO_METER);
  }
  return Math.round(feet);
}

// ============================================================================
// RACE DISTANCES
// ============================================================================

const RACE_DISTANCES = {
  marathon: { imperial: 26.2, metric: 42.195 },
  half_marathon: { imperial: 13.1, metric: 21.0975 },
  '10k': { imperial: 6.21371, metric: 10.0 },
  '5k': { imperial: 3.10686, metric: 5.0 },
} as const;

/**
 * Get race distance in user's preferred units
 *
 * @param raceType - Race type: "marathon", "half_marathon", "10k", "5k"
 * @param unitSystem - User's preferred unit system
 * @returns Distance in miles (imperial) or kilometers (metric)
 */
export function getRaceDistance(
  raceType: keyof typeof RACE_DISTANCES,
  unitSystem: UnitSystem
): number {
  return RACE_DISTANCES[raceType][unitSystem];
}

/**
 * Format race distance for display
 *
 * @param raceType - Race type: "marathon", "half_marathon", "10k", "5k"
 * @param unitSystem - User's preferred unit system
 * @returns Formatted string like "26.2 mi" or "42.2 km"
 */
export function formatRaceDistance(
  raceType: keyof typeof RACE_DISTANCES,
  unitSystem: UnitSystem
): string {
  const distance = getRaceDistance(raceType, unitSystem);
  const unit = unitSystem === 'metric' ? 'km' : 'mi';
  return `${distance} ${unit}`;
}

// ============================================================================
// UNIT LABELS (for UI components)
// ============================================================================

/**
 * Get unit labels for UI display
 *
 * @param unitSystem - User's preferred unit system
 * @returns Object with unit labels
 */
export function getUnitLabels(unitSystem: UnitSystem) {
  return {
    distance: unitSystem === 'metric' ? 'Kilometers' : 'Miles',
    distanceAbbrev: unitSystem === 'metric' ? 'km' : 'mi',
    pace: unitSystem === 'metric' ? 'Minutes per Kilometer' : 'Minutes per Mile',
    paceAbbrev: unitSystem === 'metric' ? 'min/km' : 'min/mi',
    elevation: unitSystem === 'metric' ? 'Meters' : 'Feet',
    elevationAbbrev: unitSystem === 'metric' ? 'm' : 'ft',
  };
}
