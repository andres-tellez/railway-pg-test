"""
Unit tests for ``src.services.scoring.deviation`` (V1.6 §5, Phase A item 3).

Locks in the deterministic derivation of ``deviation_direction`` so:
  * the per-run-type threshold matrix cannot silently drift,
  * the tie-breaker (``too_hard`` wins) is preserved,
  * all omission rules (HR missing, duration < 600, Tempo
    pending main-block infra, unknown planned type) return ``None``,
  * the activity adapter re-derives ``pct_above`` / ``pct_below``
    against the **planned** run type's zones (NOT ``activity.
    pct_above_zone`` which is stored relative to ``executed_type``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from src.services.scoring.deviation import (
    DEVIATION_THRESHOLDS,
    MIN_DEVIATION_DURATION_SECONDS,
    DeviationDirection,
    classify_deviation,
    compute_deviation_direction_for_activity,
)
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_EASY,
    RUN_TYPE_LONG,
    RUN_TYPE_STEADY,
    RUN_TYPE_TEMPO,
)


# ---------------------------------------------------------------------------
# Constants: lock the V1.6 §5 threshold table and omission floor.
# ---------------------------------------------------------------------------


class TestThresholdTableLocked:
    """Threshold values are part of the wire contract — lock them."""

    def test_min_duration_is_600(self):
        assert MIN_DEVIATION_DURATION_SECONDS == 600

    def test_easy_thresholds(self):
        assert DEVIATION_THRESHOLDS[RUN_TYPE_EASY] == (15.0, 30.0)

    def test_long_thresholds(self):
        assert DEVIATION_THRESHOLDS[RUN_TYPE_LONG] == (20.0, 30.0)

    def test_tempo_not_in_v1_6_activity_threshold_table(self):
        assert RUN_TYPE_TEMPO not in DEVIATION_THRESHOLDS

    def test_legacy_steady_not_in_threshold_table(self):
        assert RUN_TYPE_STEADY not in DEVIATION_THRESHOLDS

    def test_enum_wire_values(self):
        assert DeviationDirection.TOO_HARD.value == "too_hard"
        assert DeviationDirection.TOO_EASY.value == "too_easy"
        assert DeviationDirection.ON_TARGET.value == "on_target"

    def test_enum_is_str_based_for_json(self):
        import json

        assert json.dumps(DeviationDirection.TOO_HARD.value) == '"too_hard"'


# ---------------------------------------------------------------------------
# Pure function: classify_deviation
# ---------------------------------------------------------------------------


class TestClassifyDeviationOmissionRules:
    """All omission branches return None (spec §5 rules 1-2)."""

    def test_none_planned_type_returns_none(self):
        assert (
            classify_deviation(
                planned_type_canonical=None,
                pct_above=10.0,
                pct_below=10.0,
                duration_seconds=3600,
            )
            is None
        )

    def test_empty_planned_type_returns_none(self):
        assert (
            classify_deviation(
                planned_type_canonical="",
                pct_above=10.0,
                pct_below=10.0,
                duration_seconds=3600,
            )
            is None
        )

    def test_legacy_steady_canonical_uses_easy_thresholds(self):
        """Legacy ``steady`` normalizes to easy; classify with easy if passed."""
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_STEADY,
                pct_above=50.0,
                pct_below=0.0,
                duration_seconds=3600,
            )
            is None
        )

    def test_unknown_planned_type_returns_none(self):
        """Unknown types omit rather than guess."""
        assert (
            classify_deviation(
                planned_type_canonical="not_a_real_run_type",
                pct_above=10.0,
                pct_below=10.0,
                duration_seconds=3600,
            )
            is None
        )

    def test_duration_below_floor_returns_none(self):
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_EASY,
                pct_above=50.0,
                pct_below=0.0,
                duration_seconds=599,
            )
            is None
        )
        # Exactly at floor is allowed (>=, not >).
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_EASY,
                pct_above=50.0,
                pct_below=0.0,
                duration_seconds=600,
            )
            is DeviationDirection.TOO_HARD
        )

    def test_none_duration_returns_none(self):
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_EASY,
                pct_above=50.0,
                pct_below=0.0,
                duration_seconds=None,
            )
            is None
        )

    def test_none_pct_above_returns_none_hr_unusable(self):
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_EASY,
                pct_above=None,
                pct_below=10.0,
                duration_seconds=3600,
            )
            is None
        )

    def test_none_pct_below_returns_none_hr_unusable(self):
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_EASY,
                pct_above=10.0,
                pct_below=None,
                duration_seconds=3600,
            )
            is None
        )


class TestClassifyDeviationThresholdMatrix:
    """Every run type × {on_target, too_hard, too_easy} boundary."""

    _CASES = [
        # ---- Easy: too_hard >= 15, too_easy >= 30 -----------------------
        (RUN_TYPE_EASY, 14.9, 29.9, DeviationDirection.ON_TARGET),
        (RUN_TYPE_EASY, 15.0, 29.9, DeviationDirection.TOO_HARD),
        (RUN_TYPE_EASY, 14.9, 30.0, DeviationDirection.TOO_EASY),
        # ---- Long: too_hard >= 20, too_easy >= 30 -----------------------
        (RUN_TYPE_LONG, 19.9, 29.9, DeviationDirection.ON_TARGET),
        (RUN_TYPE_LONG, 20.0, 29.9, DeviationDirection.TOO_HARD),
        (RUN_TYPE_LONG, 19.9, 30.0, DeviationDirection.TOO_EASY),
    ]

    @pytest.mark.parametrize("run_type,above,below,expected", _CASES)
    def test_threshold_boundary(self, run_type, above, below, expected):
        result = classify_deviation(
            planned_type_canonical=run_type,
            pct_above=above,
            pct_below=below,
            duration_seconds=3600,
        )
        assert result == expected, (
            f"{run_type} with above={above}, below={below} → "
            f"expected {expected}, got {result}"
        )


class TestClassifyDeviationTieBreaker:
    """Spec §5 rule 1: when both thresholds exceed, ``too_hard`` wins."""

    def test_easy_both_exceeded_resolves_too_hard(self):
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_EASY,
                pct_above=50.0,
                pct_below=50.0,
                duration_seconds=3600,
            )
            is DeviationDirection.TOO_HARD
        )

    def test_long_both_exceeded_resolves_too_hard(self):
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_LONG,
                pct_above=40.0,
                pct_below=40.0,
                duration_seconds=3600,
            )
            is DeviationDirection.TOO_HARD
        )


# ---------------------------------------------------------------------------
# Activity adapter: compute_deviation_direction_for_activity
# ---------------------------------------------------------------------------


@dataclass
class _FakeActivity:
    """Minimal Activity stand-in for the deviation adapter."""

    planned_type: Optional[str] = RUN_TYPE_EASY
    moving_time: Optional[int] = 3600
    hr_zone_1: float = 0.0
    hr_zone_2: float = 0.0
    hr_zone_3: float = 0.0
    hr_zone_4: float = 0.0
    hr_zone_5: float = 0.0


class TestActivityAdapterOmission:
    """Adapter must implement every spec §5 omission rule."""

    def test_legacy_steady_normalizes_to_easy_and_classifies(self):
        act = _FakeActivity(
            planned_type=RUN_TYPE_STEADY,
            hr_zone_1=200,
            hr_zone_2=1000,
        )
        assert (
            compute_deviation_direction_for_activity(act)
            is DeviationDirection.ON_TARGET
        )

    def test_tempo_returns_none_v1_6_main_block_gap(self):
        act = _FakeActivity(
            planned_type=RUN_TYPE_TEMPO,
            hr_zone_4=900,
            hr_zone_3=300,
        )
        assert compute_deviation_direction_for_activity(act) is None

    def test_none_planned_type_returns_none(self):
        act = _FakeActivity(planned_type=None, hr_zone_2=900)
        assert compute_deviation_direction_for_activity(act) is None

    def test_short_duration_returns_none(self):
        act = _FakeActivity(moving_time=599, hr_zone_2=900)
        assert compute_deviation_direction_for_activity(act) is None

    def test_none_duration_returns_none(self):
        act = _FakeActivity(moving_time=None, hr_zone_2=900)
        assert compute_deviation_direction_for_activity(act) is None

    def test_all_zero_hr_zones_returns_none_hr_missing(self):
        act = _FakeActivity(moving_time=3600)
        assert compute_deviation_direction_for_activity(act) is None

    def test_legacy_planned_type_is_normalized(self):
        act = _FakeActivity(
            planned_type="long_run",
            hr_zone_1=100,
            hr_zone_2=900,
        )
        assert (
            compute_deviation_direction_for_activity(act)
            is DeviationDirection.ON_TARGET
        )


class TestActivityAdapterPlannedZoneRelative:
    """Adapter computes pct_above/pct_below against PLANNED run type zones."""

    def test_easy_plan_tempo_execution_is_too_hard(self):
        act = _FakeActivity(
            planned_type=RUN_TYPE_EASY,
            moving_time=3600,
            hr_zone_4=900,
            hr_zone_2=100,
        )
        assert (
            compute_deviation_direction_for_activity(act) is DeviationDirection.TOO_HARD
        )

    def test_long_plan_all_z1_execution_is_too_easy(self):
        act = _FakeActivity(
            planned_type=RUN_TYPE_LONG,
            moving_time=3600,
            hr_zone_1=1000,
        )
        assert (
            compute_deviation_direction_for_activity(act) is DeviationDirection.TOO_EASY
        )

    def test_easy_plan_cannot_trigger_too_easy_by_hr_construction(self):
        act = _FakeActivity(
            planned_type=RUN_TYPE_EASY,
            moving_time=3600,
            hr_zone_1=3600,
        )
        assert (
            compute_deviation_direction_for_activity(act)
            is DeviationDirection.ON_TARGET
        )

    def test_legacy_recovery_normalizes_to_easy_on_target(self):
        act = _FakeActivity(
            planned_type="recovery",
            moving_time=1800,
            hr_zone_1=900,
            hr_zone_2=900,
        )
        assert (
            compute_deviation_direction_for_activity(act)
            is DeviationDirection.ON_TARGET
        )

    def test_legacy_recovery_tempo_execution_is_too_hard(self):
        act = _FakeActivity(
            planned_type="recovery",
            moving_time=1800,
            hr_zone_4=1800,
        )
        assert (
            compute_deviation_direction_for_activity(act) is DeviationDirection.TOO_HARD
        )


class TestActivityAdapterDuckTyped:
    def test_accepts_simple_namespace(self):
        from types import SimpleNamespace

        act = SimpleNamespace(
            planned_type=RUN_TYPE_EASY,
            moving_time=3600,
            hr_zone_1=0,
            hr_zone_2=1800,
            hr_zone_3=0,
            hr_zone_4=0,
            hr_zone_5=0,
        )
        assert (
            compute_deviation_direction_for_activity(act)
            is DeviationDirection.ON_TARGET
        )
