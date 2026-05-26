from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.models import (
    EasyGyorReference,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_easy import (
    EasyHrProgressReference,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    EasyPaceProgressReference,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_threshold import (
    ThresholdPaceProgressReference,
)


@dataclass(frozen=True)
class GoalAlignedPaceBands:
    """
    Goal-derived pace bands computed from race target time.

    These are intentionally separate from activity/HR-derived pace bands so GYOR and
    coaching can anchor to goal-derived targets without redefining Z2 physiology.
    """

    easy: PaceZoneBand
    z3: PaceZoneBand
    z4: PaceZoneBand
    marathon: PaceZoneBand
    marathon_sec: int
    source_target_time: str


@dataclass(frozen=True)
class TrainingPaceRecommendations:
    """
    Composite pace recommendation payload with source transparency.

    ``pace_progress`` is the Insights Easy Avg Pace chart authority (HR-free).
    ``threshold_pace_progress`` is the Insights Tempo Avg Pace chart authority (Z3 corridor).
    ``hr_progress`` is the Insights Avg HR chart authority (Z2 high cap).
    ``goal_aligned_easy_pace`` is the full goal easy envelope (+55…+85).
    ``easy_gyor`` is Z2 HR target metadata when calibrated (not used for charts).
    """

    phase: str
    source_target_time: Optional[str]
    activity_easy_pace: Optional[PaceZoneBand]
    activity_z3_pace: Optional[PaceZoneBand]
    activity_z4_pace: Optional[PaceZoneBand]
    goal_aligned_easy_pace: Optional[PaceZoneBand]
    goal_aligned_z3_pace: Optional[PaceZoneBand]
    goal_aligned_z4_pace: Optional[PaceZoneBand]
    goal_aligned_marathon_pace: Optional[PaceZoneBand]
    pace_progress: Optional[EasyPaceProgressReference] = None
    threshold_pace_progress: Optional[ThresholdPaceProgressReference] = None
    hr_progress: Optional[EasyHrProgressReference] = None
    easy_gyor: Optional[EasyGyorReference] = None
    phase_source: Optional[str] = None
    phase_week_start: Optional[str] = None
