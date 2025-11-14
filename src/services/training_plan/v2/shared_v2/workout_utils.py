"""
Workout Utilities V2 (copied from original module).
"""

from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

FLOAT_COMPARISON_TOLERANCE = 0.01
DESCRIPTION_TRUNCATE_LENGTH = 50
PACE_RANGE_THRESHOLD = 1.0
DEFAULT_MAX_STEPS_IN_SUMMARY = 5


def seconds_to_pace_str(seconds: float) -> str:
    if seconds < 0:
        raise ValueError(f"Pace cannot be negative: {seconds}")
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def pace_str_to_seconds(pace_str: str) -> float:
    if not pace_str:
        raise ValueError("Pace string cannot be empty")
    pace_str = pace_str.replace("/mi", "").strip()
    parts = pace_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid pace format: {pace_str}. Expected MM:SS")
    minutes = int(parts[0])
    seconds = int(parts[1])
    if minutes < 0 or seconds < 0 or seconds >= 60:
        raise ValueError(f"Invalid pace values: {pace_str}")
    return minutes * 60 + seconds


def pace_range_to_str(min_sec: float, max_sec: float) -> str:
    if min_sec < 0 or max_sec < 0:
        raise ValueError(f"Pace cannot be negative: min={min_sec}, max={max_sec}")
    if min_sec > max_sec:
        raise ValueError(f"Min pace ({min_sec}) cannot be greater than max ({max_sec})")
    if abs(min_sec - max_sec) < PACE_RANGE_THRESHOLD:
        return f"{seconds_to_pace_str(min_sec)}/mi"
    return f"{seconds_to_pace_str(min_sec)}—{seconds_to_pace_str(max_sec)}/mi"


def normalize_segments(seg_data: Any) -> Optional[Dict[str, Any]]:
    if not seg_data:
        return None
    if isinstance(seg_data, dict):
        return seg_data
    if isinstance(seg_data, str):
        try:
            return json.loads(seg_data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug("Failed to parse segments JSON: %s", e)
            return None
    return None


def segments_are_equal(old_segments: Any, new_segments: Any) -> bool:
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
    normalized = normalize_segments(segments)
    if not normalized or not isinstance(normalized, dict):
        return None
    steps = normalized.get("steps", [])
    if not steps:
        return None
    for step in steps:
        name = step.get("name", "").lower()
        if "warm" not in name and "cool" not in name:
            return step
    return steps[1] if len(steps) > 1 else (steps[0] if steps else None)


def get_workout_pace_label_key(workout_type: str) -> str:
    if not workout_type:
        return "E"
    workout_type_lower = workout_type.lower()
    if "easy" in workout_type_lower or "recovery" in workout_type_lower:
        return "E"
    if "steady" in workout_type_lower or "aerobic" in workout_type_lower:
        return "S"
    if "endurance" in workout_type_lower or "medium" in workout_type_lower:
        return "S"
    if "long" in workout_type_lower:
        return "E"
    if "tempo" in workout_type_lower or "threshold" in workout_type_lower:
        return "T"
    if "marathon" in workout_type_lower:
        return "M"
    return "E"


def extract_pace_zone_from_workout(workout_data: Dict[str, Any]) -> str:
    target_zone = workout_data.get("target_zone")
    if target_zone:
        return target_zone
    workout_type = workout_data.get("type", "")
    pace_labels = workout_data.get("pace_labels", {})
    if pace_labels:
        label_key = get_workout_pace_label_key(workout_type)
        pace_str = pace_labels.get(label_key, "")
        if pace_str:
            return pace_str
        for key in ["E", "S", "M", "T"]:
            if key in pace_labels and pace_labels[key]:
                return pace_labels[key]
    main_segment = extract_main_segment(workout_data.get("segments"))
    if main_segment:
        target = main_segment.get("target", {})
        if isinstance(target, dict):
            pace_min = target.get("low")
            pace_max = target.get("high")
            if pace_min is not None and pace_max is not None:
                return pace_range_to_str(pace_min, pace_max)
    return ""


def validate_workout_data(workout_data: Dict[str, Any]) -> bool:
    if not isinstance(workout_data, dict):
        return False
    required_fields = ["type"]
    for field in required_fields:
        if field not in workout_data:
            logger.warning("Missing required field in workout data: %s", field)
            return False
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
                                "Invalid pace in workout: low=%s, high=%s", low, high
                            )
                            return False
                        if low > high:
                            logger.warning(
                                "Invalid pace range: low=%s > high=%s", low, high
                            )
                            return False
    return True


def validate_pace_string(pace_str: str) -> bool:
    try:
        pace_str_to_seconds(pace_str)
        return True
    except ValueError:
        return False
