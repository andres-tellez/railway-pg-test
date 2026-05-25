from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand, PaceZoneBand

GyorBand = Literal["green", "yellow", "orange", "red"]
EasyPaceProgressBand = Literal["ahead", "green", "yellow", "orange", "red"]
PaceProgressChartColor = Literal["ahead", "green", "yellow", "orange", "red"]
GyorPaceDirection = Literal["inside", "fast", "slow"]
GyorBandChartZone = dict[str, float | str]


@dataclass(frozen=True)
class GyorPacePosition:
    band: GyorBand
    direction: GyorPaceDirection


@dataclass(frozen=True)
class EasyGyorReference:
    """Static easy targets: HR Z2 band + goal easy pace.

    ``pace_zones_chart`` follows **pace-progress** semantics on the Insights app
    (ahead stripe, target corridor, slow-side Y/O/R). :func:`classify_easy_gyor`
    still applies HR-first fusion when used elsewhere.
    """

    policy: str
    hr_target_z2: HrZoneBand
    goal_aligned_easy_pace: PaceZoneBand
    pace_progress_easy_corridor: Optional[PaceZoneBand]
    pace_zones_chart: tuple[GyorBandChartZone, ...]


@dataclass(frozen=True)
class EasyGyorClassification:
    band: GyorBand
    band_hr: Optional[GyorBand]
    band_pace: Optional[GyorBand]
    pace_direction: Optional[GyorPaceDirection]
