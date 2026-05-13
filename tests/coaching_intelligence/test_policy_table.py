"""Regression: policy_table snapshot matches Wave 1 centralized thresholds."""

from __future__ import annotations

from src.coaching_intelligence.policy.policy_table import (
    POLICY_VERSION,
    snapshot_for_tests,
)

_EXPECTED_SNAPSHOT = {
    "POLICY_VERSION": "policy.v1.0",
    "sub3_seconds": 10800,
    "competitive_marathon_max_seconds": 12600,
    "marathon_distance_mi": 26.2,
    "sub3_established_min_mpw": 30.0,
    "sub3_adequate_long_run_miles": 14.0,
    "sub3_very_low_mpw": 20.0,
    "sub3_short_long_run_miles": 10.0,
    "short_timeline_weeks": 16.0,
    "completion_marathon_critical_weeks": 8.0,
    "consistency_lookback_min_weeks": 4,
    "consistency_active_week_ratio_warn": 0.35,
    "consistency_weekly_spread_mi_warn": 30.0,
    "consistency_min_completed_weeks_for_spread": 3,
    "effort_control_min_runs": 4,
    "moderate_perf_easy_gap_warn_sec": 50.0,
    "moderate_perf_sustained_gap_warn_sec": 45.0,
    "competitive_perf_easy_gap_bad_sec": 115.0,
    "competitive_perf_easy_gap_warn_sec": 72.0,
    "competitive_perf_sustained_gap_bad_sec": 95.0,
    "competitive_perf_sustained_gap_warn_sec": 58.0,
    "longest_run_durability_floor_mi": 8.0,
    "completion_marathon_short_ramp_long_run_mi": 6.0,
    "completion_marathon_short_ramp_mpw": 18.0,
    "mpw_thin_max": 15.0,
    "mpw_moderate_max": 30.0,
    "required_plan_fields": [
        "race_distance",
        "race_date",
        "primary_goal",
        "training_days",
    ],
}


def test_policy_version_constant_matches_snapshot():
    assert POLICY_VERSION == _EXPECTED_SNAPSHOT["POLICY_VERSION"]


def test_policy_table_snapshot_matches_legacy_wave1_values():
    assert snapshot_for_tests() == _EXPECTED_SNAPSHOT
