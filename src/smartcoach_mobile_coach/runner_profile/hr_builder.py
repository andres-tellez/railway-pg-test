from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.db.dao.user_profile_dao import get_user_profile
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.services.heart_rate.karvonen_zone_service import KarvonenZoneService
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    HrZoneComputation,
)
from src.utils.hr_zone_constants import STRAVA_HR_ZONES

logger = logging.getLogger(__name__)

_ZONE_KEYS = ("z1", "z2", "z3", "z4", "z5")


def apply_integer_zone_ownership(
    bands: dict[str, HrZoneBand],
) -> dict[str, HrZoneBand]:
    """
    Enforce non-overlapping integer bpm ownership on already-rounded zone bands.

    When adjacent zones share a boundary integer (``z_n.high == z_{n+1}.low``),
    the lower zone keeps that integer; the upper zone's ``low`` is raised by one.
    ``z1.low`` and ``z5.high`` are never changed.
    """
    if not bands:
        return bands

    for key, band in bands.items():
        if band.low > band.high:
            raise ValueError(
                f"Invalid HR zone band before integer ownership: {key} "
                f"low={band.low} high={band.high}"
            )

    adjusted: dict[str, HrZoneBand] = dict(bands)
    for lower_key, upper_key in zip(_ZONE_KEYS, _ZONE_KEYS[1:]):
        if lower_key not in adjusted or upper_key not in adjusted:
            continue
        lower = adjusted[lower_key]
        upper = adjusted[upper_key]
        if lower.high != upper.low:
            continue
        adjusted[upper_key] = HrZoneBand(low=upper.low + 1, high=upper.high)

    for key in _ZONE_KEYS:
        if key not in adjusted:
            continue
        band = adjusted[key]
        if band.low > band.high:
            raise ValueError(
                f"Invalid HR zone band after integer ownership: {key} "
                f"low={band.low} high={band.high}"
            )

    return adjusted


def _pct_max_zones(max_hr: int) -> dict[str, tuple[float, float]]:
    return {
        zone_key: (max_hr * low, max_hr * high)
        for zone_key, (low, high) in STRAVA_HR_ZONES.items()
    }


def compute_hr_zones(session: Session, user_id: str) -> Optional[HrZoneComputation]:
    """
    Canonical HR zone computation for runner profile.

    This is the single point that should own zone math for new code.
    Legacy writers can delegate here while they remain in compatibility mode.
    """
    profile = get_user_profile(session, user_id)
    if not profile:
        return None

    trusted_max_hr = HRMaxResolutionService.get_trusted_max_hr_for_zones(profile)
    if not trusted_max_hr:
        return None

    max_hr = int(round(float(trusted_max_hr)))
    resting_hr_raw = profile.get("resting_hr")
    resting_hr_used: Optional[int] = None

    zones: dict[str, tuple[float, float]]
    method = "pct_max"

    if isinstance(resting_hr_raw, (int, float)) and resting_hr_raw > 0:
        try:
            resting_hr_used = int(round(float(resting_hr_raw)))
            result = KarvonenZoneService.calculate_zones(max_hr, resting_hr_used)
            zones = result.zones or {}
            method = "karvonen"
        except ValueError as exc:
            logger.warning(
                "Karvonen zone calc failed for user %s (%s), using pct_max fallback",
                user_id,
                exc,
            )
            zones = _pct_max_zones(max_hr)
            resting_hr_used = None
    else:
        zones = _pct_max_zones(max_hr)

    if not zones:
        return None

    out: dict[str, HrZoneBand] = {}
    for key in ("Z1", "Z2", "Z3", "Z4", "Z5"):
        lo, hi = zones.get(key, (None, None))
        if lo is None or hi is None:
            continue
        out[key.lower()] = HrZoneBand(
            low=int(round(float(lo))), high=int(round(float(hi)))
        )

    if "z2" not in out:
        return None

    out = apply_integer_zone_ownership(out)

    return HrZoneComputation(
        zones=out,
        method=method,
        hrmax_used=max_hr,
        resting_hr_used=resting_hr_used,
    )
