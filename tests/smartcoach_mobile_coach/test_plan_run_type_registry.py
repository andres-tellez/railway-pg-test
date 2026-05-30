"""Tests for plan run type registry SSOT."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    PRIMARY_RUN_TYPES,
    RUN_TYPE_EASY,
    RUN_TYPE_HILLS,
    RUN_TYPE_INTERVALS,
    RUN_TYPE_LONG,
    RUN_TYPE_TEMPO,
    RUN_TYPE_THRESHOLD,
    SECONDARY_RUN_TYPES,
    iter_run_type_registry_payload,
    normalize_run_type_key,
    pace_zone_key_for_run_type,
    resolve_run_type,
)
from src.smartcoach_mobile_coach.runner_profile.service import (
    pace_band_seconds_for_run_type,
)
from src.smartcoach_mobile_coach.runner_profile.models import (
    PaceZoneBand,
    PaceZoneComputation,
)
from datetime import datetime, timezone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("easy", "easy"),
        ("recovery", "easy"),
        ("steady", "easy"),
        ("fartlek", "easy"),
        ("endurance", "long"),
        ("long", "long"),
        ("long_run", "long"),
        ("tempo", "tempo"),
        ("threshold", "threshold"),
        ("intervals", "intervals"),
        ("hills", "hills"),
        ("vo2", "intervals"),
        ("repetitions", "intervals"),
        ("race", "intervals"),
        ("shakeout", "easy"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_run_type_key_maps_legacy_values(raw, expected):
    assert normalize_run_type_key(raw) == expected


def test_threshold_is_distinct_canonical_from_tempo():
    tempo = resolve_run_type("tempo")
    threshold = resolve_run_type("threshold")
    assert tempo.canonical_key == RUN_TYPE_TEMPO
    assert threshold.canonical_key == RUN_TYPE_THRESHOLD
    assert tempo.pace_zone_key == "z3"
    assert threshold.pace_zone_key == "z4"
    assert tempo.insights_system == "tempo"
    assert threshold.insights_system == "threshold"


def test_legacy_steady_and_recovery_resolve_to_easy():
    assert resolve_run_type("steady").canonical_key == RUN_TYPE_EASY
    assert resolve_run_type("recovery").canonical_key == RUN_TYPE_EASY


def test_pace_zone_key_for_taxonomy_types():
    assert pace_zone_key_for_run_type("tempo") == "z3"
    assert pace_zone_key_for_run_type("threshold") == "z4"
    assert pace_zone_key_for_run_type("steady") == "z2"
    assert pace_zone_key_for_run_type("vo2") == "z4"
    assert pace_zone_key_for_run_type("intervals") == "z4"
    assert pace_zone_key_for_run_type("easy") == "z2"
    assert pace_zone_key_for_run_type("long_run", has_marathon_finish=True) == "m"


def test_registry_payload_primary_and_secondary():
    entries = {e["key"]: e for e in iter_run_type_registry_payload()}
    assert set(entries.keys()) == set(PRIMARY_RUN_TYPES + SECONDARY_RUN_TYPES)

    threshold = entries[RUN_TYPE_THRESHOLD]
    assert threshold["display_name"] == "Threshold"
    assert threshold["pace_zone_key"] == "z4"
    assert threshold["insights_system"] == "threshold"
    assert threshold["tier"] == "primary"
    assert "threshold" in threshold["legacy_aliases"]

    intervals = entries[RUN_TYPE_INTERVALS]
    assert intervals["tier"] == "secondary"
    assert intervals["primary_run_type"] == RUN_TYPE_THRESHOLD
    assert "vo2" in intervals["legacy_aliases"]

    hills = entries[RUN_TYPE_HILLS]
    assert hills["tier"] == "secondary"
    assert hills["primary_run_type"] == RUN_TYPE_THRESHOLD


def test_pace_band_seconds_matches_zone_keys():
    pace_zones = PaceZoneComputation(
        pace_z2=PaceZoneBand(low_sec=600, high_sec=630, display="10:00-10:30"),
        pace_z3=PaceZoneBand(low_sec=540, high_sec=570, display="9:00-9:30"),
        pace_z4=PaceZoneBand(low_sec=480, high_sec=510, display="8:00-8:30"),
        pace_source="test",
        pace_computed_at=datetime.now(timezone.utc),
        marathon_sec=420,
        week1_long_cap=None,
    )
    low, high = pace_band_seconds_for_run_type(pace_zones, "tempo")
    assert (low, high) == (540, 570)
    low, high = pace_band_seconds_for_run_type(pace_zones, "threshold")
    assert (low, high) == (480, 510)
    low, high = pace_band_seconds_for_run_type(pace_zones, "intervals")
    assert (low, high) == (480, 510)
    low, high = pace_band_seconds_for_run_type(pace_zones, "easy")
    assert (low, high) == (600, 630)


def test_run_type_spec_key_alias():
    spec = resolve_run_type(RUN_TYPE_TEMPO)
    assert spec.key == RUN_TYPE_TEMPO
    assert spec.key == spec.canonical_key

    long_spec = resolve_run_type(RUN_TYPE_LONG)
    assert long_spec.display_name == "Long"
