from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_easy import (
    build_easy_hr_progress_zones_chart,
    classify_easy_hr_progress,
    format_hr_z2_range_display,
    format_hr_z2_target_display,
)


def _z2() -> HrZoneBand:
    return HrZoneBand(low=120, high=145)


def test_hr_progress_target_display_is_cap():
    assert format_hr_z2_target_display(_z2()) == "≤145 bpm"


def test_hr_progress_range_display_for_help_copy():
    assert format_hr_z2_range_display(_z2()) == "120–145 bpm"


def test_hr_progress_at_or_below_cap_is_green():
    z = _z2()
    assert classify_easy_hr_progress(avg_hr_bpm=130.0, target_hr_z2=z) == "green"
    assert classify_easy_hr_progress(avg_hr_bpm=145.0, target_hr_z2=z) == "green"
    assert classify_easy_hr_progress(avg_hr_bpm=117.0, target_hr_z2=z) == "green"


def test_hr_progress_above_cap_tiers():
    z = _z2()
    assert classify_easy_hr_progress(avg_hr_bpm=146.0, target_hr_z2=z) == "yellow"
    assert classify_easy_hr_progress(avg_hr_bpm=148.0, target_hr_z2=z) == "yellow"
    assert classify_easy_hr_progress(avg_hr_bpm=149.0, target_hr_z2=z) == "orange"
    assert classify_easy_hr_progress(avg_hr_bpm=152.0, target_hr_z2=z) == "orange"
    assert classify_easy_hr_progress(avg_hr_bpm=153.0, target_hr_z2=z) == "red"
    assert classify_easy_hr_progress(avg_hr_bpm=170.0, target_hr_z2=z) == "red"


def test_hr_progress_zones_cap_model():
    zones = build_easy_hr_progress_zones_chart(_z2())
    colors = [x["color"] for x in zones]
    assert colors[0] == "green"
    green = next(x for x in zones if x["color"] == "green")
    assert float(green["max"]) == 145.0
    yellow = next(x for x in zones if x["color"] == "yellow")
    assert float(yellow["min"]) == 145.0
    assert float(yellow["max"]) == 148.0
    orange = next(x for x in zones if x["color"] == "orange")
    assert float(orange["min"]) == 148.0
    assert float(orange["max"]) == 152.0
    red = next(x for x in zones if x["color"] == "red")
    assert float(red["min"]) == 152.0
