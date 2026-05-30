"""Tests for plan workout taxonomy display helpers and wire functions."""

from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_EASY,
    RUN_TYPE_RACE,
    RUN_TYPE_THRESHOLD,
)
from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
    PRIMARY_WORKOUT_TYPES,
    SECONDARY_WORKOUT_TYPES,
    WORKOUT_DEFINITIONS,
    WORKOUT_TYPES,
    canonical_run_type_for_taxonomy,
    iter_plan_workout_taxonomy_payload,
    persisted_run_type_key_for_taxonomy,
    placement_role_for_taxonomy,
    taxonomy_pace_guidance,
    taxonomy_short_label,
    workout_display_label,
)


def test_workout_types_allowlist():
    assert WORKOUT_TYPES == frozenset(
        {"easy", "tempo", "threshold", "long_run", "intervals", "hills"}
    )
    assert PRIMARY_WORKOUT_TYPES == frozenset(
        {"easy", "tempo", "threshold", "long_run"}
    )
    assert SECONDARY_WORKOUT_TYPES == frozenset({"intervals", "hills"})
    assert len(WORKOUT_DEFINITIONS) == 6


def test_workout_display_label_from_taxonomy():
    assert workout_display_label("easy") == "Easy"
    assert workout_display_label("long_run") == "Long Run"
    assert workout_display_label("tempo") == "Tempo"
    assert workout_display_label("threshold") == "Threshold"
    assert workout_display_label("intervals") == "Intervals"
    assert workout_display_label("race") == "Race Day"


def test_taxonomy_short_label_delegates_to_display_label():
    assert taxonomy_short_label("threshold") == "Threshold"
    assert taxonomy_short_label("hills") == "Hills"


def test_taxonomy_pace_guidance_from_definition():
    assert taxonomy_pace_guidance("easy") == "Easy"
    assert taxonomy_pace_guidance("tempo") == (
        "Tempo (comfortably hard, can speak in short phrases)"
    )
    assert (
        taxonomy_pace_guidance("threshold") == "Threshold (slightly faster than tempo)"
    )


def test_taxonomy_helpers_default_for_empty():
    assert taxonomy_short_label("") == "Easy"
    assert taxonomy_pace_guidance("") == "Easy"
    assert workout_display_label("") == "Easy"


def test_persisted_run_type_key_for_taxonomy():
    assert persisted_run_type_key_for_taxonomy("easy") == "easy"
    assert persisted_run_type_key_for_taxonomy("long_run") == "long_run"
    assert persisted_run_type_key_for_taxonomy("tempo") == "tempo"
    assert persisted_run_type_key_for_taxonomy("threshold") == "threshold"
    assert placement_role_for_taxonomy("tempo") == "tempo"


def test_athlete_label_for_plan_workout():
    from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
        athlete_label_for_plan_workout,
    )

    assert athlete_label_for_plan_workout(workout_type="Tempo") == "Tempo"
    assert (
        athlete_label_for_plan_workout(
            workout_type="Easy Run",
            canonical_run_type_key="easy",
            taxonomy_key="easy",
        )
        == "Easy Run"
    )
    assert (
        athlete_label_for_plan_workout(
            canonical_run_type_key="long_run",
            taxonomy_key="long_run",
        )
        == "Long Run"
    )
    assert (
        athlete_label_for_plan_workout(
            workout_type="long_run",
            canonical_run_type_key="long_run",
        )
        == "Long Run"
    )


def test_resolve_taxonomy_and_placement():
    from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
        resolve_taxonomy_and_placement,
    )

    assert resolve_taxonomy_and_placement("tempo") == ("tempo", "tempo")
    assert resolve_taxonomy_and_placement("threshold") == ("threshold", "threshold")
    assert resolve_taxonomy_and_placement("long_run") == ("long_run", "long_run")
    assert resolve_taxonomy_and_placement("long") == ("long_run", "long_run")
    assert resolve_taxonomy_and_placement("Race") == ("race", "race")
    assert resolve_taxonomy_and_placement("steady") == ("easy", "easy")
    assert canonical_run_type_for_taxonomy("threshold") == RUN_TYPE_THRESHOLD
    assert canonical_run_type_for_taxonomy("steady") == RUN_TYPE_EASY
    assert canonical_run_type_for_taxonomy("recovery") == RUN_TYPE_EASY
    assert canonical_run_type_for_taxonomy("race") == RUN_TYPE_RACE


def test_taxonomy_payload_includes_wire_fields():
    entries = {e["key"]: e for e in iter_plan_workout_taxonomy_payload()}
    threshold = entries["threshold"]
    assert threshold["display_name"] == "Threshold"
    assert "placement_role" not in threshold
    assert threshold["canonical_run_type_key"] == "threshold"
    assert threshold["tier"] == "primary"

    intervals = entries["intervals"]
    assert intervals["tier"] == "secondary"
    assert intervals["primary_run_type"] == "threshold"
