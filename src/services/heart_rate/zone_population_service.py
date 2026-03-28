"""
Zone Population Service

Reads user profile HR data, computes zone bounds via KarvonenZoneService
(or falls back to simple %maxHR), and upserts into user_hr_zones table.

This is the ONLY writer to user_hr_zones — SQL views only read from it.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.dao.user_profile_dao import get_user_profile
from src.services.heart_rate.karvonen_zone_service import KarvonenZoneService
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.utils.hr_zone_constants import STRAVA_HR_ZONES

logger = logging.getLogger(__name__)


def refresh_user_zones(session: Session, user_id: str) -> Optional[dict]:
    """
    Compute HR zone bounds for a user and upsert into user_hr_zones.

    Resolution order:
    1. Karvonen (needs max_hr + resting_hr)
    2. Simple % of max HR (needs max_hr only)
    3. None — no zones if max_hr unavailable

    Returns dict of zone bounds on success, None if insufficient data.
    """
    profile = get_user_profile(session, user_id)
    if not profile:
        logger.info("No profile for user %s — skipping zone refresh", user_id)
        return None

    max_hr = HRMaxResolutionService.get_effective_max_hr(profile)
    if not max_hr:
        max_hr = profile.get("max_hr")
    if not max_hr:
        logger.info("No effective max_hr for user %s — skipping zone refresh", user_id)
        return None

    resting_hr = profile.get("resting_hr")

    zones: dict
    method: str

    if resting_hr and resting_hr > 0:
        try:
            result = KarvonenZoneService.calculate_zones(int(max_hr), int(resting_hr))
            zones = result.zones
            method = "karvonen"
        except ValueError as e:
            logger.warning(
                "Karvonen failed for user %s (%s), falling back to pct_max",
                user_id,
                e,
            )
            zones = _pct_max_zones(max_hr)
            method = "pct_max"
            resting_hr = None
    else:
        zones = _pct_max_zones(max_hr)
        method = "pct_max"

    row = {
        "user_id": user_id,
        "z1_low": round(zones["Z1"][0], 1),
        "z1_high": round(zones["Z1"][1], 1),
        "z2_low": round(zones["Z2"][0], 1),
        "z2_high": round(zones["Z2"][1], 1),
        "z3_low": round(zones["Z3"][0], 1),
        "z3_high": round(zones["Z3"][1], 1),
        "z4_low": round(zones["Z4"][0], 1),
        "z4_high": round(zones["Z4"][1], 1),
        "z5_low": round(zones["Z5"][0], 1),
        "z5_high": round(zones["Z5"][1], 1) if "Z5" in zones else float(max_hr),
        "method": method,
        "hrmax_used": float(max_hr),
        "resting_hr_used": float(resting_hr) if resting_hr else None,
        "computed_at": datetime.utcnow(),
    }

    session.execute(
        text(
            """
            INSERT INTO user_hr_zones (
                user_id,
                z1_low, z1_high, z2_low, z2_high,
                z3_low, z3_high, z4_low, z4_high,
                z5_low, z5_high,
                method, hrmax_used, resting_hr_used, computed_at
            ) VALUES (
                CAST(:user_id AS uuid),
                :z1_low, :z1_high, :z2_low, :z2_high,
                :z3_low, :z3_high, :z4_low, :z4_high,
                :z5_low, :z5_high,
                :method, :hrmax_used, :resting_hr_used, :computed_at
            )
            ON CONFLICT (user_id) DO UPDATE SET
                z1_low = EXCLUDED.z1_low,
                z1_high = EXCLUDED.z1_high,
                z2_low = EXCLUDED.z2_low,
                z2_high = EXCLUDED.z2_high,
                z3_low = EXCLUDED.z3_low,
                z3_high = EXCLUDED.z3_high,
                z4_low = EXCLUDED.z4_low,
                z4_high = EXCLUDED.z4_high,
                z5_low = EXCLUDED.z5_low,
                z5_high = EXCLUDED.z5_high,
                method = EXCLUDED.method,
                hrmax_used = EXCLUDED.hrmax_used,
                resting_hr_used = EXCLUDED.resting_hr_used,
                computed_at = EXCLUDED.computed_at
        """
        ),
        row,
    )
    session.commit()

    logger.info(
        "Refreshed zones for user %s: method=%s, z2=%.1f–%.1f",
        user_id,
        method,
        row["z2_low"],
        row["z2_high"],
    )
    return row


def _pct_max_zones(max_hr: float) -> dict:
    """Fallback: simple percentage-of-max-HR zones from STRAVA_HR_ZONES."""
    return {
        name: (max_hr * low, max_hr * high)
        for name, (low, high) in STRAVA_HR_ZONES.items()
    }
