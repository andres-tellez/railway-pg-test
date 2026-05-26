"""Unit tests for tempo/Z3 pace-progress corridor authority."""

from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.goal_aligned_pace import (
    compute_goal_aligned_pace_bands,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_tempo import (
    DEFAULT_PACE_PROGRESS_TEMPO_CONFIG,
    build_tempo_pace_progress_reference,
    build_tempo_pace_progress_zones_chart,
    classify_tempo_pace_progress,
    tempo_corridor_sec,
)


def _goal_z3() -> PaceZoneBand:
    goal = compute_goal_aligned_pace_bands("3:40:00")
    assert goal is not None
    return goal.z3


def test_corridor_edges_match_goal_z3():
    z3 = _goal_z3()
    fast, slow = tempo_corridor_sec(z3)
    assert fast == float(z3.low_sec)
    assert slow == float(z3.high_sec)
    assert fast < slow


def test_inside_corridor_is_green():
    z3 = _goal_z3()
    fast, slow = tempo_corridor_sec(z3)
    mid = (fast + slow) / 2.0
    assert (
        classify_tempo_pace_progress(pace_sec_per_mi=fast, goal_aligned_z3_pace=z3)
        == "green"
    )
    assert (
        classify_tempo_pace_progress(pace_sec_per_mi=slow, goal_aligned_z3_pace=z3)
        == "green"
    )
    assert (
        classify_tempo_pace_progress(pace_sec_per_mi=mid, goal_aligned_z3_pace=z3)
        == "green"
    )


def test_outside_corridor_bilateral_bands():
    z3 = _goal_z3()
    fast, slow = tempo_corridor_sec(z3)
    cfg = DEFAULT_PACE_PROGRESS_TEMPO_CONFIG

    assert (
        classify_tempo_pace_progress(
            pace_sec_per_mi=slow + 5.0, goal_aligned_z3_pace=z3
        )
        == "yellow"
    )
    assert (
        classify_tempo_pace_progress(
            pace_sec_per_mi=slow + 15.0, goal_aligned_z3_pace=z3
        )
        == "orange"
    )
    assert (
        classify_tempo_pace_progress(
            pace_sec_per_mi=slow + 40.0, goal_aligned_z3_pace=z3
        )
        == "red"
    )

    assert (
        classify_tempo_pace_progress(
            pace_sec_per_mi=fast - 5.0, goal_aligned_z3_pace=z3
        )
        == "yellow"
    )
    assert (
        classify_tempo_pace_progress(
            pace_sec_per_mi=fast - 15.0, goal_aligned_z3_pace=z3
        )
        == "orange"
    )
    assert (
        classify_tempo_pace_progress(
            pace_sec_per_mi=fast - 40.0, goal_aligned_z3_pace=z3
        )
        == "red"
    )
    assert cfg.yellow_gap_sec == 10.0
    assert cfg.orange_gap_sec == 25.0


def test_reference_uses_goal_z3_display():
    z3 = _goal_z3()
    ref = build_tempo_pace_progress_reference(z3)
    assert ref.target_tempo_pace.low_sec == z3.low_sec
    assert ref.target_tempo_pace.high_sec == z3.high_sec
    assert ref.target_display == z3.display
    assert len(ref.pace_zones_chart) >= 5
    green = next(z for z in ref.pace_zones_chart if z["color"] == "green")
    assert float(green["min"]) == float(z3.low_sec) / 60.0
    assert float(green["max"]) == float(z3.high_sec) / 60.0


def test_zones_include_bilateral_tiers():
    z3 = _goal_z3()
    zones = build_tempo_pace_progress_zones_chart(z3)
    colors = [z["color"] for z in zones]
    assert colors.count("green") == 1
    assert colors.count("yellow") == 2
    assert colors.count("orange") == 2
    assert colors.count("red") == 2
