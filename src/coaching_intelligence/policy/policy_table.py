"""
Single source for readiness-related numeric thresholds (Wave 1).

Values match historical literals in plan_generation_readiness, ambition_gap,
and pre_generation_runner_review.
"""

from __future__ import annotations

from typing import Any, Final, Tuple

POLICY_VERSION: Final[str] = "policy.v1.0"

# --- Marathon / goal time ---
sub3_seconds: Final[int] = 3 * 60 * 60
competitive_marathon_max_seconds: Final[int] = 3 * 3600 + 30 * 60  # 3:30:00
marathon_distance_mi: Final[float] = 26.2

# Piecewise-linear demand curve for marathon time goals (Phase 4).
# Each tuple is (marathon_finish_clock_seconds, demand_score). Must be sorted
# ascending by seconds (faster race = lower seconds). Demand decreases toward 0.0
# as finish time slows (higher seconds).
MARATHON_DEMAND_BANDS: Final[Tuple[Tuple[float, float], ...]] = (
    (2 * 3600 + 50 * 60, 1.0),  # 2:50 → highest demand
    (5 * 3600 + 30 * 60, 0.0),  # 5:30 → completion-oriented demand
)

# Minimum weeks before race recommended for marathon time-goal plans (interpolate by demand).
marathon_min_weeks_before_race_low_demand: Final[float] = 10.0
marathon_min_weeks_before_race_high_demand: Final[float] = 24.0

# --- Sub-3 structural gates ---
sub3_established_min_mpw: Final[float] = 30.0
sub3_adequate_long_run_miles: Final[float] = 14.0
sub3_very_low_mpw: Final[float] = 20.0
sub3_short_long_run_miles: Final[float] = 10.0

# --- Timeline ---
short_timeline_weeks: Final[float] = 16.0
completion_marathon_critical_weeks: Final[float] = 8.0

# --- Consistency ---
consistency_lookback_min_weeks: Final[int] = 4
consistency_active_week_ratio_warn: Final[float] = 0.35
consistency_weekly_spread_mi_warn: Final[float] = 30.0
consistency_min_completed_weeks_for_spread: Final[int] = 3

# --- Effort control (pace deviation signal) ---
effort_control_min_runs: Final[int] = 4

# --- Moderate marathon pace alignment (sec/mi behind goal pace) ---
moderate_perf_easy_gap_warn_sec: Final[float] = 50.0
moderate_perf_sustained_gap_warn_sec: Final[float] = 45.0

# --- Competitive marathon pace alignment ---
competitive_perf_easy_gap_bad_sec: Final[float] = 115.0
competitive_perf_easy_gap_warn_sec: Final[float] = 72.0
competitive_perf_sustained_gap_bad_sec: Final[float] = 95.0
competitive_perf_sustained_gap_warn_sec: Final[float] = 58.0

# --- Long-run / durability pattern ---
longest_run_durability_floor_mi: Final[float] = 8.0

# --- Completion marathon short-ramp heuristic ---
completion_marathon_short_ramp_long_run_mi: Final[float] = 6.0
completion_marathon_short_ramp_mpw: Final[float] = 18.0

# --- Ambition-gap weekly volume bands (mpw) ---
mpw_thin_max: Final[float] = 15.0
mpw_moderate_max: Final[float] = 30.0

# --- Required plan_request fields for readiness ---
required_plan_fields: Final[Tuple[str, ...]] = (
    "race_distance",
    "race_date",
    "primary_goal",
    "training_days",
)


def snapshot_for_tests() -> dict[str, Any]:
    """Stable dict for regression tests (values only)."""
    return {
        "POLICY_VERSION": POLICY_VERSION,
        "sub3_seconds": sub3_seconds,
        "competitive_marathon_max_seconds": competitive_marathon_max_seconds,
        "marathon_distance_mi": marathon_distance_mi,
        "MARATHON_DEMAND_BANDS": list(MARATHON_DEMAND_BANDS),
        "marathon_min_weeks_before_race_low_demand": marathon_min_weeks_before_race_low_demand,
        "marathon_min_weeks_before_race_high_demand": marathon_min_weeks_before_race_high_demand,
        "sub3_established_min_mpw": sub3_established_min_mpw,
        "sub3_adequate_long_run_miles": sub3_adequate_long_run_miles,
        "sub3_very_low_mpw": sub3_very_low_mpw,
        "sub3_short_long_run_miles": sub3_short_long_run_miles,
        "short_timeline_weeks": short_timeline_weeks,
        "completion_marathon_critical_weeks": completion_marathon_critical_weeks,
        "consistency_lookback_min_weeks": consistency_lookback_min_weeks,
        "consistency_active_week_ratio_warn": consistency_active_week_ratio_warn,
        "consistency_weekly_spread_mi_warn": consistency_weekly_spread_mi_warn,
        "consistency_min_completed_weeks_for_spread": consistency_min_completed_weeks_for_spread,
        "effort_control_min_runs": effort_control_min_runs,
        "moderate_perf_easy_gap_warn_sec": moderate_perf_easy_gap_warn_sec,
        "moderate_perf_sustained_gap_warn_sec": moderate_perf_sustained_gap_warn_sec,
        "competitive_perf_easy_gap_bad_sec": competitive_perf_easy_gap_bad_sec,
        "competitive_perf_easy_gap_warn_sec": competitive_perf_easy_gap_warn_sec,
        "competitive_perf_sustained_gap_bad_sec": competitive_perf_sustained_gap_bad_sec,
        "competitive_perf_sustained_gap_warn_sec": competitive_perf_sustained_gap_warn_sec,
        "longest_run_durability_floor_mi": longest_run_durability_floor_mi,
        "completion_marathon_short_ramp_long_run_mi": completion_marathon_short_ramp_long_run_mi,
        "completion_marathon_short_ramp_mpw": completion_marathon_short_ramp_mpw,
        "mpw_thin_max": mpw_thin_max,
        "mpw_moderate_max": mpw_moderate_max,
        "required_plan_fields": list(required_plan_fields),
    }
