from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.recommendations.goal_aligned_pace import (
    compute_goal_aligned_pace_bands,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    pace_progress_target_from_goal_easy,
)


def test_pace_progress_target_from_goal_easy_band():
    goal = compute_goal_aligned_pace_bands("3:40:00")
    assert goal is not None

    target = pace_progress_target_from_goal_easy(goal.easy)
    assert target.low_sec == target.high_sec
    assert target.low_sec == goal.easy.low_sec
