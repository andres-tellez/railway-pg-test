from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_tempo import (
    build_tempo_hr_progress_zones_chart,
    classify_tempo_hr_progress,
    format_hr_z3_target_display,
)


def _z3() -> HrZoneBand:
    return HrZoneBand(low=146, high=160)


def test_tempo_hr_progress_target_display_is_corridor():
    assert format_hr_z3_target_display(_z3()) == "146–160 bpm"


def test_tempo_hr_progress_inside_z3_is_green():
    z = _z3()
    assert classify_tempo_hr_progress(avg_hr_bpm=150.0, target_hr_z3=z) == "green"
    assert classify_tempo_hr_progress(avg_hr_bpm=146.0, target_hr_z3=z) == "green"
    assert classify_tempo_hr_progress(avg_hr_bpm=160.0, target_hr_z3=z) == "green"


def test_tempo_hr_progress_above_z3_tiers():
    z = _z3()
    assert classify_tempo_hr_progress(avg_hr_bpm=161.0, target_hr_z3=z) == "yellow"
    assert classify_tempo_hr_progress(avg_hr_bpm=163.0, target_hr_z3=z) == "yellow"
    assert classify_tempo_hr_progress(avg_hr_bpm=164.0, target_hr_z3=z) == "orange"
    assert classify_tempo_hr_progress(avg_hr_bpm=167.0, target_hr_z3=z) == "orange"
    assert classify_tempo_hr_progress(avg_hr_bpm=168.0, target_hr_z3=z) == "red"


def test_tempo_hr_progress_below_z3_tiers():
    z = _z3()
    assert classify_tempo_hr_progress(avg_hr_bpm=145.0, target_hr_z3=z) == "yellow"
    assert classify_tempo_hr_progress(avg_hr_bpm=143.0, target_hr_z3=z) == "yellow"
    assert classify_tempo_hr_progress(avg_hr_bpm=142.0, target_hr_z3=z) == "orange"
    assert classify_tempo_hr_progress(avg_hr_bpm=139.0, target_hr_z3=z) == "orange"
    assert classify_tempo_hr_progress(avg_hr_bpm=138.0, target_hr_z3=z) == "red"


def test_tempo_hr_progress_zones_corridor_model():
    zones = build_tempo_hr_progress_zones_chart(_z3())
    colors = [x["color"] for x in zones]
    assert colors.count("green") == 1
    green = next(x for x in zones if x["color"] == "green")
    assert float(green["min"]) == 146.0
    assert float(green["max"]) == 160.0
