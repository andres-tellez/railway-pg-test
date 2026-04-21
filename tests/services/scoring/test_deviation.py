"""
Unit tests for ``src.services.scoring.deviation`` (V1.6 §5, Phase A item 3).

Locks in the deterministic derivation of ``deviation_direction`` so:
  * the per-run-type threshold matrix cannot silently drift,
  * the tie-breaker (``too_hard`` wins) is preserved,
  * all omission rules (HR missing, duration < 600, Steady, Tempo
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
from src.utils.run_type_constants import (
    RUN_TYPE_EASY,
    RUN_TYPE_LONG,
    RUN_TYPE_RECOVERY,
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

    def test_recovery_thresholds(self):
        assert DEVIATION_THRESHOLDS[RUN_TYPE_RECOVERY] == (5.0, 40.0)

    def test_easy_thresholds(self):
        assert DEVIATION_THRESHOLDS[RUN_TYPE_EASY] == (15.0, 30.0)

    def test_tempo_thresholds_present_for_future_main_block_callers(self):
        """Tempo is in the threshold table so ``classify_deviation``
        can be called by a future main-block-aware caller, even though
        the V1.6 activity adapter still emits ``None`` for tempo."""
        assert DEVIATION_THRESHOLDS[RUN_TYPE_TEMPO] == (20.0, 25.0)

    def test_long_thresholds(self):
        assert DEVIATION_THRESHOLDS[RUN_TYPE_LONG] == (20.0, 30.0)

    def test_steady_not_in_threshold_table(self):
        """Spec §5 Steady TODO — no locked thresholds in V1.6."""
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
    """All six omission branches return None (spec §5 rules 1-2)."""

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

    def test_steady_returns_none_even_with_full_metrics(self):
        """Spec §5 Steady TODO — never classify, even if data is present."""
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
                planned_type_canonical="shakeout",
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

    # (run_type, pct_above, pct_below, expected) triples.
    # Values are chosen to sit exactly on / just below / just above the
    # V1.6 threshold boundaries to catch off-by-one drift.
    _CASES = [
        # ---- Recovery: too_hard >= 5, too_easy >= 40 --------------------
        (RUN_TYPE_RECOVERY, 0.0, 0.0, DeviationDirection.ON_TARGET),
        (RUN_TYPE_RECOVERY, 4.9, 0.0, DeviationDirection.ON_TARGET),
        (RUN_TYPE_RECOVERY, 5.0, 0.0, DeviationDirection.TOO_HARD),
        (RUN_TYPE_RECOVERY, 0.0, 39.9, DeviationDirection.ON_TARGET),
        (RUN_TYPE_RECOVERY, 0.0, 40.0, DeviationDirection.TOO_EASY),
        # ---- Easy: too_hard >= 15, too_easy >= 30 -----------------------
        (RUN_TYPE_EASY, 14.9, 29.9, DeviationDirection.ON_TARGET),
        (RUN_TYPE_EASY, 15.0, 29.9, DeviationDirection.TOO_HARD),
        (RUN_TYPE_EASY, 14.9, 30.0, DeviationDirection.TOO_EASY),
        # ---- Tempo: too_hard >= 20, too_easy >= 25 (pure-fn only) -------
        (RUN_TYPE_TEMPO, 19.9, 24.9, DeviationDirection.ON_TARGET),
        (RUN_TYPE_TEMPO, 20.0, 24.9, DeviationDirection.TOO_HARD),
        (RUN_TYPE_TEMPO, 19.9, 25.0, DeviationDirection.TOO_EASY),
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
        """Easy pct_above=50, pct_below=50 → both thresholds exceeded → too_hard."""
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
        """Long pct_above=40, pct_below=40 → too_hard wins over too_easy."""
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_LONG,
                pct_above=40.0,
                pct_below=40.0,
                duration_seconds=3600,
            )
            is DeviationDirection.TOO_HARD
        )

    def test_recovery_at_both_thresholds_exactly_resolves_too_hard(self):
        """Pathological: exactly at both thresholds → still too_hard."""
        assert (
            classify_deviation(
                planned_type_canonical=RUN_TYPE_RECOVERY,
                pct_above=5.0,
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
    """Minimal Activity stand-in for the deviation adapter.

    ``hr_zone_1..5`` are treated as relative weights (seconds-like),
    not percentages — matches the production Activity columns.
    """

    planned_type: Optional[str] = RUN_TYPE_EASY
    moving_time: Optional[int] = 3600
    hr_zone_1: float = 0.0
    hr_zone_2: float = 0.0
    hr_zone_3: float = 0.0
    hr_zone_4: float = 0.0
    hr_zone_5: float = 0.0


class TestActivityAdapterOmission:
    """Adapter must implement every spec §5 omission rule."""

    def test_steady_planned_type_returns_none(self):
        act = _FakeActivity(
            planned_type=RUN_TYPE_STEADY,
            hr_zone_2=900,
            hr_zone_3=300,
        )
        assert compute_deviation_direction_for_activity(act) is None

    def test_tempo_returns_none_v1_6_main_block_gap(self):
        """V1.6 gap: tempo requires main-block metrics; adapter emits
        ``None`` until that infrastructure lands. Spec §5 rule 3
        forbids full-run approximation."""
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
        act = _FakeActivity(moving_time=3600)  # zones all 0.0 default
        assert compute_deviation_direction_for_activity(act) is None

    def test_legacy_planned_type_is_normalized(self):
        """Adapter runs ``normalize_run_type_key`` — ``long_run`` → ``long``."""
        # Long target = Z2 (approx). Put 90% time in Z2 → pct_above = 0,
        # pct_below = (Z1 fraction). Leave plenty in target so neither
        # threshold trips.
        act = _FakeActivity(
            planned_type="long_run",
            hr_zone_1=100,  # below target
            hr_zone_2=900,  # in target
        )
        assert (
            compute_deviation_direction_for_activity(act)
            is DeviationDirection.ON_TARGET
        )


class TestActivityAdapterPlannedZoneRelative:
    """
    CRITICAL: the adapter must compute ``pct_above`` / ``pct_below``
    against the PLANNED run type's zones, not the executed type's.

    Without this, a run planned Easy (Z1-Z2) that was executed as
    Tempo (Z4) would score ``on_target`` because
    ``activity.pct_above_zone`` is tempo-relative (~0%). The
    deviation-direction contract demands Easy-relative → pct_above
    very high → ``too_hard``.
    """

    def test_easy_plan_tempo_execution_is_too_hard(self):
        """Planned Easy (Z1-Z2 target), 90% time in Z4 → TOO_HARD."""
        act = _FakeActivity(
            planned_type=RUN_TYPE_EASY,
            moving_time=3600,
            hr_zone_4=900,  # way above Easy's target band
            hr_zone_2=100,  # small amount in target
        )
        assert (
            compute_deviation_direction_for_activity(act) is DeviationDirection.TOO_HARD
        )

    def test_long_plan_all_z1_execution_is_too_easy(self):
        """Planned Long (target Z2), 100% time in Z1 → pct_below_target
        = 100% ≥ 30% → TOO_EASY. This is the canonical test that
        target-band semantics (not acceptable-band) are used: under
        acceptable-band semantics Long's ``acceptable_zone_min`` = 1
        would make pct_below always 0 and too_easy unreachable."""
        act = _FakeActivity(
            planned_type=RUN_TYPE_LONG,
            moving_time=3600,
            hr_zone_1=1000,
        )
        assert (
            compute_deviation_direction_for_activity(act) is DeviationDirection.TOO_EASY
        )

    def test_easy_plan_cannot_trigger_too_easy_by_hr_construction(self):
        """Known V1 HR-model behavior: Easy's target is Z1-Z2 and
        sub-Z1 HR samples are filtered upstream, so Easy can never
        trigger ``too_easy`` via HR zones — only via pace, which is
        out of scope for deviation_direction in V1.6. 100% Z1 (below
        target Z2 but still inside Easy's acceptable band) must
        resolve to ON_TARGET, not TOO_EASY. Documented in module
        docstring 'Target-band vs acceptable-band'."""
        act = _FakeActivity(
            planned_type=RUN_TYPE_EASY,
            moving_time=3600,
            hr_zone_1=3600,
        )
        assert (
            compute_deviation_direction_for_activity(act)
            is DeviationDirection.ON_TARGET
        )

    def test_recovery_plan_executed_on_target_returns_on_target(self):
        """Planned Recovery (Z1 target), all time in Z1 → ON_TARGET."""
        act = _FakeActivity(
            planned_type=RUN_TYPE_RECOVERY,
            moving_time=1800,
            hr_zone_1=1800,
        )
        assert (
            compute_deviation_direction_for_activity(act)
            is DeviationDirection.ON_TARGET
        )

    def test_recovery_plan_tempo_execution_is_too_hard(self):
        """Recovery planned (Z1), 100% Z4 → far above → TOO_HARD."""
        act = _FakeActivity(
            planned_type=RUN_TYPE_RECOVERY,
            moving_time=1800,
            hr_zone_4=1800,
        )
        assert (
            compute_deviation_direction_for_activity(act) is DeviationDirection.TOO_HARD
        )


class TestActivityAdapterDuckTyped:
    """The adapter should tolerate dict-like inputs and missing attributes."""

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
