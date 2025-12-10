/**
 * Pace Zone Formatting Utilities
 *
 * Helper functions for formatting pace zone data for display.
 * Uses existing unitFormatters for actual conversion logic.
 */

import { formatPace, formatPaceRange, UnitSystem } from './unitFormatters';
import type { PaceZonesResponse, PaceZone } from '@/types/paceZones';

/**
 * Format a pace zone range for display
 */
export function formatPaceZoneRange(
  zone: PaceZone,
  unitSystem: UnitSystem = 'imperial'
): string {
  return formatPaceRange(zone.min, zone.max, unitSystem);
}

/**
 * Format marathon pace (single value) for display
 */
export function formatMarathonPace(
  pace: number,
  unitSystem: UnitSystem = 'imperial'
): string {
  return formatPace(pace, unitSystem);
}

/**
 * Get formatted pace string for a zone type
 */
export function getFormattedPaceForZone(
  paceZones: PaceZonesResponse,
  zoneType: 'easy' | 'steady' | 'marathon' | 'threshold',
  unitSystem: UnitSystem = 'imperial'
): string {
  switch (zoneType) {
    case 'easy':
      return formatPaceZoneRange(paceZones.easy, unitSystem);
    case 'steady':
      return formatPaceZoneRange(paceZones.steady, unitSystem);
    case 'marathon':
      return formatMarathonPace(paceZones.marathon.pace, unitSystem);
    case 'threshold':
      return formatPaceZoneRange(paceZones.threshold, unitSystem);
    default:
      return '';
  }
}

/**
 * Convert seconds per mile to percentage position on spectrum
 * (0% = slowest pace, 100% = fastest pace)
 */
export function paceToPercentage(
  secondsPerMile: number,
  minPace: number,
  maxPace: number
): number {
  if (maxPace === minPace) return 50; // Avoid division by zero
  // Invert: faster pace (lower seconds) = higher percentage
  return ((maxPace - secondsPerMile) / (maxPace - minPace)) * 100;
}

/**
 * Get the full pace range (min to max) across all zones
 */
export function getFullPaceRange(paceZones: PaceZonesResponse): {
  min: number;
  max: number;
} {
  const allPaces = [
    paceZones.threshold.min,
    paceZones.threshold.max,
    paceZones.marathon.pace,
    paceZones.steady.min,
    paceZones.steady.max,
    paceZones.easy.min,
    paceZones.easy.max,
  ];

  return {
    min: Math.min(...allPaces),
    max: Math.max(...allPaces),
  };
}
