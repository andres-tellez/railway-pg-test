"""
Central vocabulary for running / training terminology.

Coach-copy mirror of ``runner_profile`` plan definitions. Runtime authority for
run-type zone mapping, workout taxonomy, and placement roles lives in
``src.smartcoach_mobile_coach.runner_profile`` — import from there for plan
generation, scoring, and API payloads.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Mapping

from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
    PERSISTED_RUN_TYPE_KEYS,
    WORKOUT_DEFINITIONS as _RUNNER_PROFILE_WORKOUT_DEFINITIONS,
)

WORKOUT_TYPES: FrozenSet[str] = frozenset(_RUNNER_PROFILE_WORKOUT_DEFINITIONS.keys())

WORKOUT_DEFINITIONS: Mapping[str, Dict[str, str]] = {
    key: {
        "description": defn["description"],
        "purpose": defn["purpose"],
    }
    for key, defn in _RUNNER_PROFILE_WORKOUT_DEFINITIONS.items()
}

RUNNING_RULES: Dict[str, Any] = {
    "allowed_intensity_labels": frozenset(
        {"very_easy", "easy", "moderate", "hard", "very_hard"}
    ),
    "quality_session_min_recovery_days_after": 2,
    "weekly_long_run_taxonomy_key": "long_run",
    "persisted_run_type_keys": PERSISTED_RUN_TYPE_KEYS,
}

# Heart-rate / effort zones — placeholders for coach copy (calibrated bands from runner_profile).
ZONE_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "Z1": {
        "label": "Zone 1",
        "typical_effort": "Recovery / very easy",
        "notes": "Placeholder; align with runner_profile HR bands.",
    },
    "Z2": {
        "label": "Zone 2",
        "typical_effort": "Easy aerobic",
        "notes": "Placeholder; align with runner_profile HR bands.",
    },
    "Z3": {
        "label": "Zone 3",
        "typical_effort": "Tempo / moderate hard",
        "notes": "Placeholder; align with runner_profile HR bands.",
    },
    "Z4": {
        "label": "Zone 4",
        "typical_effort": "Threshold / hard",
        "notes": "Placeholder; align with runner_profile HR bands.",
    },
    "Z5": {
        "label": "Zone 5",
        "typical_effort": "VO2max / neuromuscular",
        "notes": "Placeholder; align with runner_profile HR bands.",
    },
}


def get_taxonomy_for_role(role: str) -> str | None:
    """Return the taxonomy key for a persisted run_type_key, or ``None`` if unknown."""
    key = str(role or "").strip().lower()
    if key in PERSISTED_RUN_TYPE_KEYS:
        return "long_run" if key == "long" else key
    return None
