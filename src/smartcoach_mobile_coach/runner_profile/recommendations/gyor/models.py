from __future__ import annotations

from dataclasses import dataclass

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand


@dataclass(frozen=True)
class EasyGyorReference:
    """HR easy-run reference (Z2 target + fusion policy).

    Insights Avg Pace chart uses ``TrainingPaceRecommendations.pace_progress``
    (HR-free). This object is not used for pace-progress band math.
    """

    policy: str
    hr_target_z2: HrZoneBand
