from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.config import (
    DEFAULT_EASY_GYOR_CONFIG,
    GyorFusionPolicy,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.models import (
    GyorBand,
    GyorPaceDirection,
    GyorPacePosition,
)

_BAND_RANK: dict[GyorBand, int] = {
    "green": 0,
    "yellow": 1,
    "orange": 2,
    "red": 3,
}


def _cap_band(band: GyorBand, max_band: GyorBand) -> GyorBand:
    if _BAND_RANK[band] <= _BAND_RANK[max_band]:
        return band
    return max_band


def fuse_gyor_hr_priority(
    *,
    band_hr: GyorBand | None,
    pace_position: GyorPacePosition | None,
    policy: GyorFusionPolicy | None = None,
) -> GyorBand | None:
    """
    HR-first GYOR fusion.

    - HR orange/red always wins.
    - HR yellow cannot be upgraded by pace.
    - HR green absolves faster-than-target pace (no downgrade for ``direction=fast``).
    - Without HR, pace-only bands are capped (default orange).
    """
    pol = policy or DEFAULT_EASY_GYOR_CONFIG.fusion
    band_pace = pace_position.band if pace_position is not None else None
    direction: GyorPaceDirection | None = (
        pace_position.direction if pace_position is not None else None
    )

    if band_hr is None and band_pace is None:
        return None
    if band_hr is None:
        assert band_pace is not None
        return _cap_band(band_pace, pol.max_band_without_hr)  # type: ignore[arg-type]

    if band_hr in ("orange", "red"):
        return band_hr
    if band_hr == "yellow":
        return "yellow"

    # HR green
    if band_pace is None or band_pace == "green":
        return "green"
    if direction == "fast":
        return "green"
    if direction == "slow":
        return band_pace if band_pace != "green" else "green"
    return band_pace
