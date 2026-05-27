"""Tests for plan run type registry SSOT."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_LONG,
    RUN_TYPE_STEADY,
    RUN_TYPE_TEMPO,
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
        ("recovery", "recovery"),
        ("steady", "steady"),
        ("endurance", "long"),
        ("long", "long"),
        ("long_run", "long"),
        ("tempo", "tempo"),
        ("threshold", "tempo"),
        ("intervals", "tempo"),
        ("hills", "tempo"),
        ("fartlek", "tempo"),
        ("race", "tempo"),
        ("shakeout", "easy"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_run_type_key_maps_legacy_values(raw, expected):
    assert normalize_run_type_key(raw) == expected


def test_steady_maps_to_tempo_z3_for_insights():
    spec = resolve_run_type("steady")
    assert spec.canonical_key == RUN_TYPE_STEADY
    assert spec.display_name == "Steady"
    assert spec.pace_zone_key == "z3"
    assert spec.hr_zone_key == "z3"
    assert spec.insights_system == "tempo"


def test_pace_zone_key_for_taxonomy_types():
    assert pace_zone_key_for_run_type("steady") == "z3"
    assert pace_zone_key_for_run_type("threshold") == "z3"
    assert pace_zone_key_for_run_type("vo2") == "z4"
    assert pace_zone_key_for_run_type("intervals") == "z4"
    assert pace_zone_key_for_run_type("easy") == "z2"
    assert pace_zone_key_for_run_type("long_run", has_marathon_finish=True) == "m"


def test_registry_payload_includes_steady():
    entries = {e["key"]: e for e in iter_run_type_registry_payload()}
    steady = entries[RUN_TYPE_STEADY]
    assert steady["display_name"] == "Steady"
    assert steady["pace_zone_key"] == "z3"
    assert steady["insights_system"] == "tempo"
    assert "steady" in steady["legacy_aliases"]


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
    low, high = pace_band_seconds_for_run_type(pace_zones, "steady")
    assert (low, high) == (540, 570)
    low, high = pace_band_seconds_for_run_type(pace_zones, "intervals")
    assert (low, high) == (480, 510)
    low, high = pace_band_seconds_for_run_type(pace_zones, "easy")
    assert (low, high) == (600, 630)


def test_run_type_spec_key_alias():
    spec = resolve_run_type(RUN_TYPE_TEMPO)
    assert spec.key == RUN_TYPE_TEMPO
    assert spec.key == spec.canonical_key
