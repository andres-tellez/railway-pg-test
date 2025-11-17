/**
 * Utility functions for normalizing workout type display names.
 * Standardizes workout types to single-word labels for consistent UI display.
 */

/**
 * Normalizes workout type to a single-word display name.
 *
 * @param workoutType - The full workout type string (e.g., "Easy / Recovery", "Aerobic / Steady")
 * @returns Single-word normalized type (e.g., "Easy", "Steady", "Endurance", "Long")
 */
export function normalizeWorkoutTypeDisplay(workoutType: string): string {
  if (!workoutType) return "";

  return workoutType
    .replace(/Easy\s*\/?\s*Recovery/gi, "Easy")
    .replace(/Long\s*Run/gi, "Long")
    .replace(/Aerobic\s*\/?\s*Steady/gi, "Steady")
    .replace(/Endurance\s*\(Medium-Long\)/gi, "Endurance")
    .trim();
}
