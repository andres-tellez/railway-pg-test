"""
Canonical run type definitions for planned vs executed classification.

This is the single source of truth for:
- Canonical run type names shown to users
- Target HR zones by run type
- Tolerance profiles for scoring
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToleranceProfile:
    """Simple v1 tolerance thresholds used for score bucketing."""

    green_min_compliance: float
    yellow_min_compliance: float
    green_max_above: float
    yellow_max_above: float


@dataclass(frozen=True)
class RunTypeDefinition:
    """
    Canonical run type definition.

    Zone ids are 1-indexed (Z1..Z5) to match activity hr_zone_1..hr_zone_5 columns.
    """

    key: str
    display_name: str
    target_zone_ids: tuple[int, ...]
    acceptable_zone_min: int
    acceptable_zone_max: int
    min_duration_seconds: int | None = None
    tolerance: ToleranceProfile | None = None


RUN_TYPE_EASY = "easy"
RUN_TYPE_RECOVERY = "recovery"
RUN_TYPE_STEADY = "steady"
RUN_TYPE_TEMPO = "tempo"
RUN_TYPE_LONG = "long"

CANONICAL_RUN_TYPES = (
    RUN_TYPE_EASY,
    RUN_TYPE_RECOVERY,
    RUN_TYPE_STEADY,
    RUN_TYPE_TEMPO,
    RUN_TYPE_LONG,
)

RUN_TYPE_DEFINITIONS: dict[str, RunTypeDefinition] = {
    RUN_TYPE_EASY: RunTypeDefinition(
        key=RUN_TYPE_EASY,
        display_name="Easy",
        target_zone_ids=(1, 2),
        acceptable_zone_min=1,
        acceptable_zone_max=3,
        min_duration_seconds=20 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=76.0,
            yellow_min_compliance=60.0,
            green_max_above=10.0,
            yellow_max_above=22.0,
        ),
    ),
    RUN_TYPE_RECOVERY: RunTypeDefinition(
        key=RUN_TYPE_RECOVERY,
        display_name="Recovery",
        target_zone_ids=(1,),
        acceptable_zone_min=1,
        acceptable_zone_max=2,
        min_duration_seconds=15 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=88.0,
            yellow_min_compliance=72.0,
            green_max_above=4.0,
            yellow_max_above=10.0,
        ),
    ),
    RUN_TYPE_STEADY: RunTypeDefinition(
        key=RUN_TYPE_STEADY,
        display_name="Steady",
        target_zone_ids=(2, 3),
        acceptable_zone_min=2,
        acceptable_zone_max=3,
        min_duration_seconds=25 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=72.0,
            yellow_min_compliance=56.0,
            green_max_above=9.0,
            yellow_max_above=20.0,
        ),
    ),
    RUN_TYPE_TEMPO: RunTypeDefinition(
        key=RUN_TYPE_TEMPO,
        display_name="Tempo",
        target_zone_ids=(3, 4),
        acceptable_zone_min=3,
        acceptable_zone_max=4,
        min_duration_seconds=20 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=66.0,
            yellow_min_compliance=50.0,
            green_max_above=12.0,
            yellow_max_above=25.0,
        ),
    ),
    RUN_TYPE_LONG: RunTypeDefinition(
        key=RUN_TYPE_LONG,
        display_name="Long",
        target_zone_ids=(2,),
        acceptable_zone_min=1,
        acceptable_zone_max=3,
        min_duration_seconds=75 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=68.0,
            yellow_min_compliance=52.0,
            green_max_above=14.0,
            yellow_max_above=27.0,
        ),
    ),
}

# Map legacy/internal workout keys to canonical run types
LEGACY_TO_CANONICAL_RUN_TYPE = {
    # Existing weekly plan distribution keys
    "easy": RUN_TYPE_EASY,
    "recovery": RUN_TYPE_RECOVERY,
    "steady": RUN_TYPE_STEADY,
    "endurance": RUN_TYPE_LONG,
    "long": RUN_TYPE_LONG,
    "long_run": RUN_TYPE_LONG,
    # Quality variants map to tempo bucket for v1 scoring
    "tempo": RUN_TYPE_TEMPO,
    "threshold": RUN_TYPE_TEMPO,
    "intervals": RUN_TYPE_TEMPO,
    "hills": RUN_TYPE_TEMPO,
    "fartlek": RUN_TYPE_TEMPO,
    "race": RUN_TYPE_TEMPO,
    "shakeout": RUN_TYPE_EASY,
}


def normalize_run_type_key(raw_value: str | None) -> str | None:
    """
    Normalize a raw run/workout type string to a canonical run type key.
    """
    if not raw_value:
        return None
    raw = str(raw_value).strip().lower()
    if not raw:
        return None
    return LEGACY_TO_CANONICAL_RUN_TYPE.get(raw)
