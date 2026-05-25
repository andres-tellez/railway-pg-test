from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.recommendations.goal_aligned_pace import (
    compute_goal_aligned_pace_bands,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    build_easy_pace_progress_zones_chart,
    classify_easy_pace_progress,
    pace_progress_target_from_goal_easy,
)


def _pace_progress_target():
    goal = compute_goal_aligned_pace_bands("3:40:00")
    assert goal is not None
    return pace_progress_target_from_goal_easy(goal.easy)


def test_pace_progress_target_from_goal_easy_band():
    goal = compute_goal_aligned_pace_bands("3:40:00")
    assert goal is not None

    target = pace_progress_target_from_goal_easy(goal.easy)
    assert target.low_sec == target.high_sec
    assert target.low_sec == goal.easy.low_sec


def test_pace_progress_faster_than_target_is_green():
    target = _pace_progress_target()
    assert (
        classify_easy_pace_progress(
            pace_sec_per_mi=float(target.low_sec) - 10.0,
            target_easy_pace=target,
        )
        == "green"
    )


def test_pace_progress_at_target_is_green():
    target = _pace_progress_target()
    assert (
        classify_easy_pace_progress(
            pace_sec_per_mi=float(target.low_sec),
            target_easy_pace=target,
        )
        == "green"
    )


def test_pace_progress_slow_tiers_vs_target():
    target = _pace_progress_target()
    t = float(target.low_sec)
    assert (
        classify_easy_pace_progress(pace_sec_per_mi=t + 10.0, target_easy_pace=target)
        == "yellow"
    )
    assert (
        classify_easy_pace_progress(pace_sec_per_mi=t + 25.0, target_easy_pace=target)
        == "orange"
    )
    assert (
        classify_easy_pace_progress(pace_sec_per_mi=t + 50.0, target_easy_pace=target)
        == "red"
    )


def test_easy_pace_progress_zones_single_target_model():
    target = _pace_progress_target()
    z = build_easy_pace_progress_zones_chart(target)
    colors = [x["color"] for x in z]
    assert colors[0] == "green"
    assert colors.count("green") == 1
    assert "yellow" in colors
    assert "red" in colors
    green = next(x for x in z if x["color"] == "green")
    assert float(green["max"]) == float(target.low_sec) / 60.0
