"""
Unit tests for ``src.services.scoring.completion``.

Locks in the V1.6 §7 / PHASE_3_IMPLEMENTATION_CHECKLIST 0.B contract:

- ``compute_completion_pct`` is the sole producer of the per-run
  completion percent (0-100 scale, unclipped on overshoot, None when
  undefined).
- ``COMPLETION_THRESHOLD_RATIO`` (0.50) and ``COMPLETION_THRESHOLD_PCT``
  (50.0) are the named constants. No call site may inline ``0.50`` or
  ``50.0`` for the "completed" gate — they must call
  ``is_run_completed(...)``.
"""

from __future__ import annotations

import pytest

from src.services.scoring.completion import (
    COMPLETION_THRESHOLD_PCT,
    COMPLETION_THRESHOLD_RATIO,
    compute_completion_pct,
    is_run_completed,
)


class TestThresholdConstants:
    """Lock V1.6 §7 thresholds as named constants, not magic numbers."""

    def test_ratio_is_0_50(self):
        assert COMPLETION_THRESHOLD_RATIO == 0.50

    def test_pct_is_50_0(self):
        assert COMPLETION_THRESHOLD_PCT == 50.0

    def test_pct_equals_100x_ratio(self):
        assert COMPLETION_THRESHOLD_PCT == COMPLETION_THRESHOLD_RATIO * 100.0


class TestComputeCompletionPct:
    """Canonical ``completion_pct`` producer."""

    def test_exactly_planned_is_100(self):
        assert compute_completion_pct(5.0, 5.0) == 100.0

    def test_half_planned_is_50(self):
        assert compute_completion_pct(2.5, 5.0) == 50.0

    def test_overshoot_not_clipped(self):
        """Values above 100 indicate overshoot — never clipped."""
        assert compute_completion_pct(6.0, 5.0) == 120.0
        assert compute_completion_pct(10.0, 5.0) == 200.0

    def test_planned_zero_returns_none(self):
        """Zero planned miles → completion is undefined."""
        assert compute_completion_pct(5.0, 0) is None
        assert compute_completion_pct(5.0, 0.0) is None

    def test_planned_negative_returns_none(self):
        """Negative planned miles → completion is undefined (guards against
        legacy bad data)."""
        assert compute_completion_pct(5.0, -1.0) is None

    def test_planned_none_returns_none(self):
        assert compute_completion_pct(5.0, None) is None

    def test_actual_none_returns_none(self):
        """No activity yet → completion is undefined, not zero."""
        assert compute_completion_pct(None, 5.0) is None

    def test_both_none_returns_none(self):
        assert compute_completion_pct(None, None) is None

    def test_actual_zero_returns_zero(self):
        """Zero actual miles with a real plan → 0 % (distinguishes from
        unplanned run, which is None)."""
        assert compute_completion_pct(0.0, 5.0) == 0.0

    def test_integer_inputs_accepted(self):
        """Callers may pass ints (GYR weekly aggregate uses ints)."""
        assert compute_completion_pct(5, 10) == 50.0

    def test_does_not_round(self):
        """Rounding is the caller's responsibility so DB (2 dp) and
        display (1 dp) surfaces can format independently."""
        result = compute_completion_pct(1.0, 3.0)
        # 33.333... — callers round as needed.
        assert result == pytest.approx(33.33333333, abs=1e-6)


class TestIsRunCompleted:
    """V1.6 §7 completed-run gate (``>= 50%`` of planned miles)."""

    def test_exactly_threshold_is_completed(self):
        assert is_run_completed(50.0) is True

    def test_above_threshold_is_completed(self):
        assert is_run_completed(75.0) is True
        assert is_run_completed(100.0) is True
        assert is_run_completed(150.0) is True

    def test_below_threshold_is_not_completed(self):
        assert is_run_completed(49.99) is False
        assert is_run_completed(25.0) is False
        assert is_run_completed(0.0) is False

    def test_none_is_not_completed(self):
        """Undefined completion (unplanned / zero-plan) is not 'completed'
        for adherence purposes per V1.6 §7."""
        assert is_run_completed(None) is False

    def test_gate_uses_named_constant_not_magic_number(self):
        """Regression guard: if someone swaps the constant's value the
        gate must follow (single source of truth)."""
        assert is_run_completed(COMPLETION_THRESHOLD_PCT) is True
        assert is_run_completed(COMPLETION_THRESHOLD_PCT - 0.01) is False
