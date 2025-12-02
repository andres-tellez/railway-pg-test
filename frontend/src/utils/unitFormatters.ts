/**
 * Unit Formatting Utilities
 *
 * Pure utility functions for converting and formatting units.
 * All functions are pure (no side effects) and can be tested in isolation.
 *
 * Input: Values in base units (miles, seconds per mile) from backend
 * Output: Formatted strings in user's preferred unit system
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
 * Format distance for display
 *
 * @param miles - Distance in miles (from backend)
 * @param unitSystem - User's preferred unit system
 * @param precision - Number of decimal places (default: 1)
 * @returns Formatted string like "5.0 mi" or "8.0 km"
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
 * Convert miles to display value (without formatting)
 *
 * @param miles - Distance in miles
 * @param unitSystem - User's preferred unit system
 * @returns Distance in miles (imperial) or kilometers (metric)
 */
export function toDisplayDistance(miles: number, unitSystem: UnitSystem): number {
  if (unitSystem === 'metric') {
    return Math.round(miles * MI_TO_KM * 10) / 10; // Round to 1 decimal
  }
  return Math.round(miles * 10) / 10;
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
