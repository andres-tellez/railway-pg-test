"""
Workout Utilities - Centralized helper functions for workout operations.

This module provides:
- Pace formatting/conversion utilities
- Segment parsing/normalization utilities
- Pace zone extraction strategy
- Workout structure formatting

All pace values are in seconds per mile.
"""

from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Floating point comparison tolerance
FLOAT_COMPARISON_TOLERANCE = 0.01

# String truncation length for descriptions
DESCRIPTION_TRUNCATE_LENGTH = 50

# Pace range comparison threshold (if difference < this, treat as single pace)
PACE_RANGE_THRESHOLD = 1.0

# Maximum steps to include in segment summary
DEFAULT_MAX_STEPS_IN_SUMMARY = 5

# ============================================================================
# PACE FORMATTING UTILITIES
# ============================================================================


def seconds_to_pace_str(seconds: float) -> str:
    """
    Convert seconds per mile to MM:SS format.

    Args:
        seconds: Pace in seconds per mile (float)

    Returns:
        Formatted string like "9:45"

    Raises:
        ValueError: If seconds is negative

    Example:
        >>> seconds_to_pace_str(585.0)
        '9:45'
    """
    if seconds < 0:
        raise ValueError(f"Pace cannot be negative: {seconds}")

    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def pace_str_to_seconds(pace_str: str) -> float:
    """
    Convert pace string (MM:SS or MM:SS/mi) to seconds per mile.

    Args:
        pace_str: Pace string like "9:45" or "9:45/mi"

    Returns:
        Total seconds per mile (float)

    Raises:
        ValueError: If pace string format is invalid

    Example:
        >>> pace_str_to_seconds("9:45")
        585.0
        >>> pace_str_to_seconds("8:30/mi")
        510.0
    """
    if not pace_str:
        raise ValueError("Pace string cannot be empty")

    # Remove "/mi" suffix if present
    pace_str = pace_str.replace("/mi", "").strip()

    try:
        parts = pace_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid pace format: {pace_str}. Expected MM:SS")

        minutes = int(parts[0])
        seconds = int(parts[1])

        if minutes < 0 or seconds < 0 or seconds >= 60:
            raise ValueError(f"Invalid pace values: {pace_str}")

        return minutes * 60 + seconds
    except (ValueError, IndexError) as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Invalid pace format: {pace_str}. Expected MM:SS") from e


def pace_range_to_str(min_sec: float, max_sec: float) -> str:
    """
    Format pace range as 'MM:SS—MM:SS/mi'.

    Args:
        min_sec: Minimum pace in seconds per mile
        max_sec: Maximum pace in seconds per mile

    Returns:
        Formatted string like "9:30—10:00/mi" or "9:45/mi" if min==max

    Raises:
        ValueError: If min_sec or max_sec is negative, or min > max
    """
    if min_sec < 0 or max_sec < 0:
        raise ValueError(f"Pace cannot be negative: min={min_sec}, max={max_sec}")
    if min_sec > max_sec:
        raise ValueError(f"Min pace ({min_sec}) cannot be greater than max ({max_sec})")

    if abs(min_sec - max_sec) < PACE_RANGE_THRESHOLD:
        return f"{seconds_to_pace_str(min_sec)}/mi"
    return f"{seconds_to_pace_str(min_sec)}—{seconds_to_pace_str(max_sec)}/mi"


# ============================================================================
# SEGMENT UTILITIES
# ============================================================================


def normalize_segments(seg_data: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize segments to dict for comparison.

    Handles:
    - Dict format: returns as-is
    - String JSON: parses to dict
    - None/empty: returns None

    Args:
        seg_data: Segments data (dict, str, or None)

    Returns:
        Normalized dict or None
    """
    if not seg_data:
        return None
    if isinstance(seg_data, dict):
        return seg_data
    if isinstance(seg_data, str):
        try:
            return json.loads(seg_data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"Failed to parse segments JSON: {e}")
            return None
    return None


def segments_are_equal(old_segments: Any, new_segments: Any) -> bool:
    """
    Deep compare two segments objects using JSON string comparison.

    Args:
        old_segments: Original segments data
        new_segments: New segments data

    Returns:
        True if segments are equivalent, False otherwise
    """
    old_norm = normalize_segments(old_segments)
    new_norm = normalize_segments(new_segments)

    if not old_norm and not new_norm:
        return True
    if not old_norm or not new_norm:
        return False

    old_json = json.dumps(old_norm, sort_keys=True)
    new_json = json.dumps(new_norm, sort_keys=True)
    return old_json == new_json


def format_segment_summary(
    seg_data: Any, max_steps: int = DEFAULT_MAX_STEPS_IN_SUMMARY
) -> str:
    """
    Format segment data into human-readable summary.

    Args:
        seg_data: Segments data to format
        max_steps: Maximum number of steps to include in summary

    Returns:
        Human-readable string like "Warmup: 1.0 mi; Easy: 4.0 mi @ 9:30-10:00/mi"
    """
    normalized = normalize_segments(seg_data)
    if not normalized:
        return "None"

    steps = normalized.get("steps", []) if isinstance(normalized, dict) else []
    if not steps:
        return "No steps"

    step_summaries = []
    for step in steps[:max_steps]:
        step_type = step.get("type", step.get("name", "unknown"))
        value = step.get("value", 0)
        unit = step.get("unit", "mi")
        target = step.get("target", {})

        pace_info = ""
        if isinstance(target, dict):
            # ✅ Use correct keys: "low" and "high" (not "paceMin"/"paceMax")
            pace_min = target.get("low")
            pace_max = target.get("high")
            if pace_min is not None and pace_max is not None:
                pace_info = f" @ {pace_range_to_str(pace_min, pace_max)}"

        step_summaries.append(f"{step_type.capitalize()}: {value} {unit}{pace_info}")

    summary = "; ".join(step_summaries)
    if len(steps) > max_steps:
        summary += f" (+ {len(steps) - max_steps} more)"

    return summary or f"{len(steps)} steps"


def extract_main_segment(segments: Any) -> Optional[Dict[str, Any]]:
    """
    Extract main running segment (skip warmup/cool-down).

    Args:
        segments: Segments data

    Returns:
        Main segment dict or None
    """
    normalized = normalize_segments(segments)
    if not normalized or not isinstance(normalized, dict):
        return None

    steps = normalized.get("steps", [])
    if not steps:
        return None

    # Find main segment (not warmup/cool-down)
    for step in steps:
        name = step.get("name", "").lower()
        if "warm" not in name and "cool" not in name:
            return step

    # Fallback: return second step (usually main after warmup), or first
    return steps[1] if len(steps) > 1 else (steps[0] if steps else None)


# ============================================================================
# PACE ZONE EXTRACTION STRATEGY
# ============================================================================


def get_workout_pace_label_key(workout_type: str) -> str:
    """
    Map workout type to pace_labels key (z2, z3, m, z4).

    Args:
        workout_type: Workout type string (e.g., "easy", "steady", "long")

    Returns:
        Pace label key: "z2", "z3", "m", or "z4"
    """
    if not workout_type:
        return "z2"

    workout_type_lower = workout_type.lower()

    if "easy" in workout_type_lower or "recovery" in workout_type_lower:
        return "z2"
    elif "steady" in workout_type_lower or "aerobic" in workout_type_lower:
        return "z3"
    elif "endurance" in workout_type_lower or "medium" in workout_type_lower:
        return "z3"
    elif "long" in workout_type_lower:
        return "z2"
    elif "tempo" in workout_type_lower or "threshold" in workout_type_lower:
        return "z4"
    elif "marathon" in workout_type_lower:
        return "m"
    else:
        return "z2"


def extract_pace_zone_from_workout(workout_data: Dict[str, Any]) -> str:
    """
    Extract pace zone string from workout data.

    Strategy (in priority order):
    1. Direct target_zone field
    2. pace_labels[workout_type_key] (z2/z3/m/z4 based on workout type)
    3. Main segment's target pace range

    Args:
        workout_data: Workout data dict with segments, pace_labels, etc.

    Returns:
        Pace zone string like "9:30—10:00/mi" or empty string if not found
    """
    # 1. Try direct target_zone
    target_zone = workout_data.get("target_zone")
    if target_zone:
        return target_zone

    # 2. Try pace_labels with correct key based on workout type
    workout_type = workout_data.get("type", "")
    pace_labels = workout_data.get("pace_labels", {})
    if pace_labels:
        # Canonical keys: z2/z3/m/z4
        label_key = get_workout_pace_label_key(workout_type)
        pace_str = pace_labels.get(label_key, "")
        if pace_str:
            return pace_str

        # Fallback: try other common zones in order
        for key in ["z2", "z3", "m", "z4"]:
            if key in pace_labels and pace_labels[key]:
                return pace_labels[key]

    # 3. Extract from main segment's target
    main_segment = extract_main_segment(workout_data.get("segments"))
    if main_segment:
        target = main_segment.get("target", {})
        if isinstance(target, dict):
            # ✅ Use correct keys: "low" and "high" (not "paceMin"/"paceMax")
            pace_min = target.get("low")
            pace_max = target.get("high")
            if pace_min is not None and pace_max is not None:
                return pace_range_to_str(pace_min, pace_max)

    return ""


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================


def validate_workout_data(workout_data: Dict[str, Any]) -> bool:
    """
    Validate workout data structure.

    Args:
        workout_data: Workout data dict

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(workout_data, dict):
        return False

    # Check required fields
    required_fields = ["type"]
    for field in required_fields:
        if field not in workout_data:
            logger.warning(f"Missing required field in workout data: {field}")
            return False

    # Validate pace if present in segments
    segments = workout_data.get("segments")
    if segments:
        normalized = normalize_segments(segments)
        if normalized and isinstance(normalized, dict):
            steps = normalized.get("steps", [])
            for step in steps:
                target = step.get("target", {})
                if isinstance(target, dict):
                    low = target.get("low")
                    high = target.get("high")
                    if low is not None and high is not None:
                        if low < 0 or high < 0:
                            logger.warning(
                                f"Invalid pace in workout: low={low}, high={high}"
                            )
                            return False
                        if low > high:
                            logger.warning(
                                f"Invalid pace range: low={low} > high={high}"
                            )
                            return False

    return True


def validate_pace_string(pace_str: str) -> bool:
    """
    Validate pace string format (MM:SS or MM:SS/mi).

    Args:
        pace_str: Pace string to validate

    Returns:
        True if valid format, False otherwise
    """
    if not pace_str or not isinstance(pace_str, str):
        return False

    # Remove "/mi" suffix if present
    pace_str = pace_str.replace("/mi", "").strip()

    try:
        parts = pace_str.split(":")
        if len(parts) != 2:
            return False

        minutes = int(parts[0])
        seconds = int(parts[1])

        return minutes >= 0 and 0 <= seconds < 60
    except (ValueError, IndexError):
        return False


# ============================================================================
# WEEKLY MILEAGE CALCULATION
# ============================================================================


def calculate_weekly_mileage_from_workouts(workouts: list) -> float:
    """
    Calculate total weekly mileage from a list of workouts.

    Single source of truth for summing workout distances.
    Handles both 'distance_miles' and 'miles' field names.

    Args:
        workouts: List of workout dictionaries with distance fields

    Returns:
        Total weekly mileage rounded to 1 decimal place

    Example:
        >>> workouts = [
        ...     {"distance_miles": 5.0, "type": "easy"},
        ...     {"miles": 8.0, "type": "steady"},
        ...     {"distance_miles": 17.0, "type": "long_run"}
        ... ]
        >>> calculate_weekly_mileage_from_workouts(workouts)
        30.0
    """
    if not workouts:
        return 0.0

    total = 0.0
    for workout in workouts:
        if not isinstance(workout, dict):
            continue
        # Try distance_miles first, then miles, then default to 0
        miles = workout.get("distance_miles") or workout.get("miles") or 0
        try:
            total += float(miles)
        except (ValueError, TypeError):
            # Skip invalid values
            continue

    return round(total, 1)
