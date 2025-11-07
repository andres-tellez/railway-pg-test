/**
 * Longest Runs Type Definitions
 * ==============================
 *
 * TypeScript interfaces for longest run comparison data.
 * Matches backend data structure from longest_runs_routes.py
 *
 * Author: SmartCoach Development Team
 * Last Updated: October 12, 2025
 */

export interface LongestRunData {
  week_start: string;
  activity_id: number;
  name: string;
  date: string;
  distance: number;
  pace: string;
  duration: string;
  heart_rate_zones: any;
  is_personal_record: boolean;
  is_significant_drop: boolean;
  trend: 'improving' | 'declining' | 'stable';
  change_pct: number;
  prev_week_distance: number | null;
}

export interface LongestRunsSummary {
  total_weeks: number;
  pr_count: number;
  drop_count: number;
  improving_weeks: number;
}

export interface LongestRunsResponse {
  runs: LongestRunData[];
  summary: LongestRunsSummary;
}

export interface LongestRunsConfig {
  time_periods: {
    default: number;
    options: number[];
  };
  thresholds: {
    pr_detection_window_weeks: number;
    significant_drop_percentage: number;
    significant_drop_min_distance: number;
    stable_threshold_percentage: number;
    improvement_min_percentage: number;
  };
}
