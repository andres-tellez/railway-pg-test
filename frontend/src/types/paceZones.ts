/**
 * Type definitions for Pace Zones
 *
 * Defines the structure of pace zone data from the API
 * and component prop types.
 */

export interface PaceZone {
  min: number; // seconds per mile
  max: number; // seconds per mile (same as min for Marathon)
}

export interface PaceZonesResponse {
  easy: PaceZone;
  steady: PaceZone;
  marathon: { pace: number }; // Single value for marathon pace
  threshold: PaceZone;
  updatedAt: string;
  source: string;
  medianEasyPace?: number;
}

export interface PaceZoneInfo {
  name: string;
  icon: string;
  color: string;
  rpe: string;
  tag: string;
  tagIcon: string;
  description: string;
  whenToUse: string;
  typicalDuration: string;
  percentage: string;
}

export type PaceZoneType = 'threshold' | 'marathon' | 'steady' | 'easy';
