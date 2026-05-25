from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import RunnerZoneProfileData
from src.smartcoach_mobile_coach.runner_profile.recommendations.goal_aligned_pace import (
    compute_goal_aligned_pace_bands,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.easy import (
    build_easy_gyor_reference,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.models import (
    TrainingPaceRecommendations,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    build_easy_pace_progress_reference,
)


def build_training_pace_recommendations(
    *,
    profile: RunnerZoneProfileData,
    target_time: str | None,
    phase: str = "Base",
    phase_source: str | None = None,
    phase_week_start: str | None = None,
) -> TrainingPaceRecommendations | None:
    goal_aligned = compute_goal_aligned_pace_bands(target_time)
    activity_easy = profile.pace_z2 if profile.calibrated else None
    activity_z3 = profile.pace_z3 if profile.calibrated else None
    activity_z4 = profile.pace_z4 if profile.calibrated else None
    goal_easy = goal_aligned.easy if goal_aligned is not None else None

    if (
        activity_easy is None
        and activity_z3 is None
        and activity_z4 is None
        and goal_aligned is None
    ):
        return None

    pace_progress = (
        build_easy_pace_progress_reference(goal_easy) if goal_easy is not None else None
    )
    easy_gyor = build_easy_gyor_reference(
        hr_target_z2=profile.hr_z2 if profile.calibrated else None,
        goal_aligned_easy_pace=goal_easy,
        pace_progress=pace_progress,
    )

    return TrainingPaceRecommendations(
        phase=str(phase or "Base"),
        source_target_time=(
            goal_aligned.source_target_time if goal_aligned is not None else None
        ),
        activity_easy_pace=activity_easy,
        activity_z3_pace=activity_z3,
        activity_z4_pace=activity_z4,
        goal_aligned_easy_pace=goal_easy,
        goal_aligned_z3_pace=(goal_aligned.z3 if goal_aligned is not None else None),
        goal_aligned_z4_pace=(goal_aligned.z4 if goal_aligned is not None else None),
        goal_aligned_marathon_pace=(
            goal_aligned.marathon if goal_aligned is not None else None
        ),
        pace_progress=pace_progress,
        easy_gyor=easy_gyor,
        phase_source=phase_source,
        phase_week_start=phase_week_start,
    )
