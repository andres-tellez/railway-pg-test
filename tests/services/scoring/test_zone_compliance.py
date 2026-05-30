"""Tests for src.services.scoring.zone_compliance.

Covers V1.6 Pre-Phase A 0.3 — single source of truth for
(in_target, pct_above, pct_below) derivation. Spec ref:
SMARTCOACH_SYSTEM_SPEC_V1.md §5; PHASE_3_IMPLEMENTATION_CHECKLIST 0.3, §X.5.
"""

from dataclasses import dataclass
from typing import Optional

import pytest

from src.services.scoring.zone_compliance import (
    ZoneMetrics,
    zone_distribution_from_activity,
    zone_metrics_for_type,
)
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_EASY,
    RUN_TYPE_LONG,
    RUN_TYPE_TEMPO,
    RUN_TYPE_THRESHOLD,
)


@dataclass
class _FakeActivity:
    """Minimal stand-in matching the _ActivityZoneReader protocol.

    Using a dataclass rather than an Activity ORM instance keeps the unit
    tests free of database setup.
    """

    hr_zone_1: Optional[float] = 0.0
    hr_zone_2: Optional[float] = 0.0
    hr_zone_3: Optional[float] = 0.0
    hr_zone_4: Optional[float] = 0.0
    hr_zone_5: Optional[float] = 0.0


class TestZoneDistributionFromActivity:
    def test_all_zeros_returns_zero_dict_without_dividing(self):
        # total == 0 must NOT cause ZeroDivisionError.
        result = zone_distribution_from_activity(_FakeActivity())
        assert result == {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}

    def test_none_values_coerce_to_zero(self):
        result = zone_distribution_from_activity(
            _FakeActivity(
                hr_zone_1=None,
                hr_zone_2=600,
                hr_zone_3=None,
                hr_zone_4=400,
                hr_zone_5=None,
            )
        )
        assert result[1] == 0.0
        assert result[2] == 60.0
        assert result[3] == 0.0
        assert result[4] == 40.0
        assert result[5] == 0.0

    def test_normalized_to_percent(self):
        # 10:20:30:30:10 (weights) -> 10%:20%:30%:30%:10%
        result = zone_distribution_from_activity(
            _FakeActivity(
                hr_zone_1=10, hr_zone_2=20, hr_zone_3=30, hr_zone_4=30, hr_zone_5=10
            )
        )
        assert result == {1: 10.0, 2: 20.0, 3: 30.0, 4: 30.0, 5: 10.0}

    def test_sum_of_percentages_is_100(self):
        result = zone_distribution_from_activity(
            _FakeActivity(
                hr_zone_1=137,
                hr_zone_2=215,
                hr_zone_3=422,
                hr_zone_4=98,
                hr_zone_5=12,
            )
        )
        assert sum(result.values()) == pytest.approx(100.0)

    def test_accepts_float_seconds(self):
        result = zone_distribution_from_activity(
            _FakeActivity(hr_zone_1=1.5, hr_zone_2=1.5, hr_zone_3=0.0)
        )
        assert result[1] == 50.0
        assert result[2] == 50.0
        assert result[3] == 0.0


class TestZoneMetricsForTypeCanonical:
    """Deterministic 10-20-30-30-10 distribution run through every run type."""

    DIST = {1: 10.0, 2: 20.0, 3: 30.0, 4: 30.0, 5: 10.0}

    def test_easy_uses_zones_1_and_2_as_target(self):
        # Easy target_zone_ids=(1,2), acceptable=[1..3], so above=Z4+Z5.
        m = zone_metrics_for_type(self.DIST, RUN_TYPE_EASY)
        assert m.in_target == 30.0
        assert m.pct_below == 0.0
        assert m.pct_above == 40.0

    def test_legacy_recovery_normalizes_to_easy(self):
        m = zone_metrics_for_type(self.DIST, "recovery")
        assert m.in_target == 30.0
        assert m.pct_above == 40.0

    def test_legacy_steady_normalizes_to_easy(self):
        m = zone_metrics_for_type(self.DIST, "steady")
        assert m.in_target == 30.0
        assert m.pct_above == 40.0

    def test_tempo_uses_zones_3_and_4_as_target(self):
        # Tempo target=(3,4), acceptable=[3..4], so below=Z1+Z2, above=Z5.
        m = zone_metrics_for_type(self.DIST, RUN_TYPE_TEMPO)
        assert m.in_target == 60.0
        assert m.pct_below == 30.0
        assert m.pct_above == 10.0

    def test_threshold_uses_zone_4_as_target(self):
        m = zone_metrics_for_type(self.DIST, RUN_TYPE_THRESHOLD)
        assert m.in_target == 30.0
        assert m.pct_below == 30.0
        assert m.pct_above == 0.0

    def test_long_uses_only_zone_2_as_target(self):
        # Long target=(2,), acceptable=[1..3], so above=Z4+Z5.
        m = zone_metrics_for_type(self.DIST, RUN_TYPE_LONG)
        assert m.in_target == 20.0
        assert m.pct_below == 0.0
        assert m.pct_above == 40.0


class TestZoneMetricsEdgeCases:
    def test_all_below_target_band(self):
        # Everything in Z1 for a tempo run: massive pct_below.
        dist = {1: 100.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
        m = zone_metrics_for_type(dist, RUN_TYPE_TEMPO)
        assert m.in_target == 0.0
        assert m.pct_below == 100.0
        assert m.pct_above == 0.0

    def test_all_above_target_band(self):
        # Everything in Z5 for an Easy run: massive pct_above.
        dist = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 100.0}
        m = zone_metrics_for_type(dist, RUN_TYPE_EASY)
        assert m.in_target == 0.0
        assert m.pct_below == 0.0
        assert m.pct_above == 100.0

    def test_in_acceptable_band_but_outside_target_counts_as_neither(self):
        # Easy: target=(1,2), acceptable=[1..3]. All time in Z3 is
        # "acceptable but not ideal" — should not count above or below.
        dist = {1: 0.0, 2: 0.0, 3: 100.0, 4: 0.0, 5: 0.0}
        m = zone_metrics_for_type(dist, RUN_TYPE_EASY)
        assert m.in_target == 0.0
        assert m.pct_below == 0.0
        assert m.pct_above == 0.0

    def test_rounding_to_two_decimal_places(self):
        # Values that force rounding (1/3 ≈ 33.333...).
        dist = {1: 33.3333333, 2: 33.3333333, 3: 33.3333334, 4: 0.0, 5: 0.0}
        m = zone_metrics_for_type(dist, RUN_TYPE_TEMPO)
        # Tempo target=(3,4): only Z3 present here
        assert m.in_target == 33.33
        assert m.pct_below == 66.67
        assert m.pct_above == 0.0

    def test_missing_zone_keys_default_to_zero(self):
        # Partial dict: any missing zone id must contribute 0, not KeyError.
        partial = {2: 80.0, 4: 20.0}
        m = zone_metrics_for_type(partial, RUN_TYPE_EASY)
        assert m.in_target == 80.0
        assert m.pct_below == 0.0
        assert m.pct_above == 20.0

    def test_unknown_run_type_falls_back_to_easy(self):
        m = zone_metrics_for_type({1: 100.0}, "not_a_real_run_type")
        assert m.in_target == 100.0


class TestZoneMetricsNamedTupleContract:
    def test_positional_unpacking_preserves_v1_order(self):
        # V1 callers rely on: in_target, above, below = zone_metrics_for_type(...)
        # Changing this order is a breaking change — lock it.
        m = zone_metrics_for_type({1: 10.0, 2: 40.0, 4: 50.0}, RUN_TYPE_EASY)
        in_target, pct_above, pct_below = m
        assert in_target == 50.0  # Z1 + Z2
        assert pct_above == 50.0  # Z4 + Z5 (Z5 = 0)
        assert pct_below == 0.0

    def test_named_attribute_access(self):
        m = zone_metrics_for_type({3: 100.0}, RUN_TYPE_TEMPO)
        assert m.in_target == 100.0
        assert m.pct_above == 0.0
        assert m.pct_below == 0.0

    def test_is_instance_of_zone_metrics(self):
        m = zone_metrics_for_type({1: 100.0}, RUN_TYPE_EASY)
        assert isinstance(m, ZoneMetrics)
        assert isinstance(m, tuple)  # NamedTuple is-a tuple
