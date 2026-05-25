from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand, PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    PaceProgressBand,
    PaceProgressChartZone,
)

GyorBand = PaceProgressBand
EasyPaceProgressBand = PaceProgressBand
GyorPaceDirection = Literal["inside", "fast", "slow"]
GyorBandChartZone = PaceProgressChartZone


@dataclass(frozen=True)
class GyorPacePosition:
    band: GyorBand
    direction: GyorPaceDirection


@dataclass(frozen=True)
class EasyGyorReference:
    """Static easy targets: HR Z2 band + goal easy pace.

    ``pace_zones_chart`` follows **pace-progress** semantics on the Insights app
    (single target easy pace, slow-side Y/O/R). :func:`classify_easy_gyor` is
    HR-fused easy classification (full easy band + Z2 HR); not used on the pace chart.
    """

    policy: str
    hr_target_z2: HrZoneBand
    goal_aligned_easy_pace: PaceZoneBand
    pace_progress_target_easy_pace: Optional[PaceZoneBand]
    pace_zones_chart: tuple[PaceProgressChartZone, ...]


@dataclass(frozen=True)
class EasyGyorClassification:
    band: GyorBand
    band_hr: Optional[GyorBand]
    band_pace: Optional[GyorBand]
    pace_direction: Optional[GyorPaceDirection]
