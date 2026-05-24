from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class HrZoneBand:
    low: int
    high: int


@dataclass(frozen=True)
class PaceZoneBand:
    low_sec: int
    high_sec: int
    display: str


@dataclass(frozen=True)
class HrZoneComputation:
    zones: dict[str, HrZoneBand]
    method: str
    hrmax_used: int
    resting_hr_used: Optional[int]


@dataclass(frozen=True)
class PaceZoneComputation:
    pace_z2: PaceZoneBand
    pace_z3: PaceZoneBand
    pace_z4: PaceZoneBand
    pace_source: str
    pace_computed_at: datetime
    marathon_sec: int
    week1_long_cap: float


@dataclass(frozen=True)
class RunnerZoneProfileData:
    user_id: str
    calibrated: bool
    computed_at: Optional[datetime]
    hrmax_used: Optional[int]
    resting_hr_used: Optional[int]
    zone_method: Optional[str]
    hr_z1: Optional[HrZoneBand]
    hr_z2: Optional[HrZoneBand]
    hr_z3: Optional[HrZoneBand]
    hr_z4: Optional[HrZoneBand]
    hr_z5: Optional[HrZoneBand]
    pace_z2: Optional[PaceZoneBand]
    pace_z3: Optional[PaceZoneBand]
    pace_z4: Optional[PaceZoneBand]
    pace_source: Optional[str]
    pace_computed_at: Optional[datetime]
