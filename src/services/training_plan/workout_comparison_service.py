"""
Workout Comparison Service - Detects changes between old and new workout data.

This service centralizes all workout change detection logic, making it:
- Testable (unit tests can test each comparison)
- Maintainable (changes in one place)
- Reusable (other services can use it)
"""

from typing import Dict, Any, List, TYPE_CHECKING
import logging

from .workout_utils import (
    segments_are_equal,
    format_segment_summary,
    extract_pace_zone_from_workout,
    FLOAT_COMPARISON_TOLERANCE,
    DESCRIPTION_TRUNCATE_LENGTH,
)

if TYPE_CHECKING:
    from src.db.models.plan_workouts import PlanWorkout

logger = logging.getLogger(__name__)


class WorkoutComparisonService:
    """Service for comparing workout data and detecting changes."""

    @staticmethod
    def detect_changes(
        old_workout: "PlanWorkout",  # PlanWorkout from DB
        new_workout_data: Dict[str, Any],  # From Pass4WorkoutDetails
    ) -> List[Dict[str, Any]]:
        """
        Detect all changes between old and new workout data.

        Compares:
        - Description/Cues
        - Intensity
        - Workout Structure (segments)
        - Target Pace Zone
        - Distance/Miles
        - Target HR

        Args:
            old_workout: PlanWorkout object from database
            new_workout_data: New workout data dict from Pass4WorkoutDetails

        Returns:
            List of change dictionaries, each with:
            - "field": Field name (e.g., "Target Pace Zone")
            - "before": Old value
            - "after": New value
        """
        changes = []

        # 1. Compare Description/Cues
        old_desc = old_workout.description or ""
        new_desc = new_workout_data.get("cues", "")
        if old_desc != new_desc:
            changes.append(
                {
                    "field": "Description/Cues",
                    "before": (
                        old_desc[:DESCRIPTION_TRUNCATE_LENGTH] + "..."
                        if len(old_desc) > DESCRIPTION_TRUNCATE_LENGTH
                        else old_desc
                    ),
                    "after": (
                        new_desc[:DESCRIPTION_TRUNCATE_LENGTH] + "..."
                        if len(new_desc) > DESCRIPTION_TRUNCATE_LENGTH
                        else new_desc
                    ),
                }
            )

        # 2. Compare Intensity
        old_intensity = old_workout.intensity or old_workout.workout_type or ""
        new_intensity = new_workout_data.get("type", old_workout.workout_type)
        if old_intensity != new_intensity:
            changes.append(
                {
                    "field": "Intensity",
                    "before": old_intensity,
                    "after": new_intensity,
                }
            )

        # 3. Compare Workout Structure (segments)
        old_segments = old_workout.segments
        new_segments = new_workout_data.get("segments")
        if not segments_are_equal(old_segments, new_segments):
            old_summary = format_segment_summary(old_segments)
            new_summary = format_segment_summary(new_segments)
            changes.append(
                {
                    "field": "Workout Structure",
                    "before": old_summary,
                    "after": new_summary,
                }
            )

        # 4. Compare Target Pace Zone
        old_target_zone = old_workout.target_zone or ""
        new_target_zone = extract_pace_zone_from_workout(new_workout_data)
        if old_target_zone != new_target_zone:
            changes.append(
                {
                    "field": "Target Pace Zone",
                    "before": old_target_zone or "Not set",
                    "after": new_target_zone or "Not set",
                }
            )

        # 5. Compare Distance/Miles
        old_miles = old_workout.miles or 0
        new_miles = new_workout_data.get("miles") or new_workout_data.get(
            "distance_mi", 0
        )
        if abs(old_miles - new_miles) > FLOAT_COMPARISON_TOLERANCE:
            changes.append(
                {
                    "field": "Distance",
                    "before": f"{old_miles:.1f} miles",
                    "after": f"{new_miles:.1f} miles",
                }
            )

        # 6. Compare Target HR
        old_target_hr = old_workout.target_hr
        new_target_hr = new_workout_data.get("target_hr")
        if old_target_hr != new_target_hr:
            changes.append(
                {
                    "field": "Target HR",
                    "before": old_target_hr or "Not set",
                    "after": new_target_hr or "Not set",
                }
            )

        return changes
