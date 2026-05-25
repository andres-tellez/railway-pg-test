"""Weekly insight easy_avg_hr_band uses hr_progress (Z2), not week-over-week trend."""

from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand
from src.smartcoach_mobile_coach.weekly_insights_service import (
    _compute_easy_system_pipeline,
)


def _z2() -> HrZoneBand:
    return HrZoneBand(low=120, high=145)


def test_easy_avg_hr_band_in_z2_is_green_despite_wow_increase():
    """146 bpm vs prior 142 would trend worse; vs Z2 high (145) it is yellow."""
    kpis = {
        "avg_hr": 146.0,
        "hr_drift_pct": 2.0,
        "z2_pace_min_per_mi": 9.5,
        "efficiency": 1.2,
    }
    prior = {
        "hr_drift_pct": 2.0,
        "z2_pace_min_per_mi": 9.6,
        "efficiency": 1.1,
        "easy_avg_hr": 142.0,
        "hr_drift_band": "green",
        "z2_pace_band": "green",
        "easy_avg_hr_band": "green",
        "efficiency_band": "green",
        "overall_band": "green",
    }
    out = _compute_easy_system_pipeline(kpis, prior, target_hr_z2=_z2())
    assert out["bands"]["easy_avg_hr"] == "yellow"


def test_easy_avg_hr_band_inside_z2_is_green():
    kpis = {
        "avg_hr": 130.0,
        "hr_drift_pct": 2.0,
        "z2_pace_min_per_mi": 9.5,
        "efficiency": 1.2,
    }
    out = _compute_easy_system_pipeline(kpis, prior=None, target_hr_z2=_z2())
    assert out["bands"]["easy_avg_hr"] == "green"


def test_easy_avg_hr_band_null_without_calibrated_z2():
    kpis = {
        "avg_hr": 130.0,
        "hr_drift_pct": 2.0,
        "z2_pace_min_per_mi": 9.5,
        "efficiency": 1.2,
    }
    out = _compute_easy_system_pipeline(kpis, prior=None, target_hr_z2=None)
    assert out["bands"]["easy_avg_hr"] is None
