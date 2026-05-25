from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand, PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.config import (
    EASY_GYOR_POLICY,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.models import (
    EasyGyorReference,
)


def build_easy_gyor_reference(
    *,
    hr_target_z2: HrZoneBand | None,
    goal_aligned_easy_pace: PaceZoneBand | None,
) -> EasyGyorReference | None:
    """Build HR easy reference when calibrated Z2 and marathon goal easy exist."""
    if hr_target_z2 is None or goal_aligned_easy_pace is None:
        return None
    return EasyGyorReference(
        policy=EASY_GYOR_POLICY,
        hr_target_z2=hr_target_z2,
    )
