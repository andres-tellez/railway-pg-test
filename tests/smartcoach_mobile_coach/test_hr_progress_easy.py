from __future__ import annotations

from datetime import datetime, timezone

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_easy import (
    build_easy_hr_progress_zones_chart,
    classify_easy_hr_progress,
    format_hr_z2_target_display,
)


def _z2() -> HrZoneBand:
    return HrZoneBand(low=120, high=145)


def test_hr_progress_target_display():
    assert format_hr_z2_target_display(_z2()) == "120–145 bpm"


def test_hr_progress_inside_z2_is_green():
    assert classify_easy_hr_progress(avg_hr_bpm=130.0, target_hr_z2=_z2()) == "green"


def test_hr_progress_at_z2_edges_is_green():
    assert classify_easy_hr_progress(avg_hr_bpm=120.0, target_hr_z2=_z2()) == "green"
    assert classify_easy_hr_progress(avg_hr_bpm=145.0, target_hr_z2=_z2()) == "green"


def test_hr_progress_outside_z2_tiers():
    z = _z2()
    assert classify_easy_hr_progress(avg_hr_bpm=148.0, target_hr_z2=z) == "yellow"
    assert classify_easy_hr_progress(avg_hr_bpm=156.0, target_hr_z2=z) == "orange"
    assert classify_easy_hr_progress(avg_hr_bpm=170.0, target_hr_z2=z) == "red"
    assert classify_easy_hr_progress(avg_hr_bpm=117.0, target_hr_z2=z) == "yellow"


def test_hr_progress_zones_include_green_z2_envelope():
    zones = build_easy_hr_progress_zones_chart(_z2())
    colors = [x["color"] for x in zones]
    assert colors[0] == "green"
    green = next(x for x in zones if x["color"] == "green")
    assert float(green["min"]) == 120.0
    assert float(green["max"]) == 145.0
