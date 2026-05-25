from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.recommendations.goal_aligned_pace import (
    compute_goal_aligned_pace_bands,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    DEFAULT_PACE_PROGRESS_EASY_CONFIG,
    compute_pace_progress_target_easy_pace,
)


def _marathon_pace_sec(target_time: str) -> float:
    cfg = DEFAULT_PACE_PROGRESS_EASY_CONFIG
    parts = target_time.split(":")
    h, m, sec = int(parts[0]), int(parts[1]), float(parts[2])
    total = float(h * 3600 + m * 60) + sec
    return total / cfg.marathon_distance_mi


def test_pace_progress_target_from_target_time():
    cfg = DEFAULT_PACE_PROGRESS_EASY_CONFIG
    marathon_sec = _marathon_pace_sec("3:40:00")

    target = compute_pace_progress_target_easy_pace("3:40:00")
    assert target is not None
    assert target.low_sec == target.high_sec
    assert target.low_sec == int(round(marathon_sec + cfg.easy_target_offset_sec))


def test_pace_progress_target_matches_goal_easy_fast_edge():
    goal = compute_goal_aligned_pace_bands("3:40:00")
    target = compute_pace_progress_target_easy_pace("3:40:00")
    assert goal is not None
    assert target is not None
    assert target.low_sec == goal.easy.low_sec
