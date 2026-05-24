from __future__ import annotations

from typing import Any, Optional

from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)

# Canonical copy for Insights › Easy banner (emitted whenever Z2 HR + Z2 pace are present).
INSIGHTS_EASY_BANNER_SUBTITLE = (
    "Stay within this HR range to keep easy runs truly easy and avoid carrying "
    "fatigue into harder days."
)


def _hr_band_payload(band: Optional[HrZoneBand]) -> Optional[dict[str, int]]:
    if band is None:
        return None
    return {"low": int(band.low), "high": int(band.high)}


def _pace_band_payload(band: Optional[PaceZoneBand]) -> Optional[dict[str, Any]]:
    if band is None:
        return None
    return {
        "low_sec": int(band.low_sec),
        "high_sec": int(band.high_sec),
        "display": band.display,
    }


def runner_zone_profile_payload(profile: RunnerZoneProfileData) -> dict[str, Any]:
    pace_zones: dict[str, Any] = {}
    for key_name, pace_band in (
        ("z2", profile.pace_z2),
        ("z3", profile.pace_z3),
        ("z4", profile.pace_z4),
    ):
        band_payload = _pace_band_payload(pace_band)
        if band_payload is not None:
            pace_zones[key_name] = band_payload

    # Banner copy rides with the profile so mobile never treats weekly plan strips as HR/Z2 authority.
    insights_easy_banner = None
    if profile.calibrated and profile.hr_z2 is not None and profile.pace_z2 is not None:
        insights_easy_banner = {"subtitle": INSIGHTS_EASY_BANNER_SUBTITLE}

    return {
        "calibrated": bool(profile.calibrated),
        "computed_at": profile.computed_at.isoformat() if profile.computed_at else None,
        "hrmax": profile.hrmax_used,
        "resting_hr": profile.resting_hr_used,
        "zone_method": profile.zone_method,
        "hr_zones": (
            {
                "z1": _hr_band_payload(profile.hr_z1),
                "z2": _hr_band_payload(profile.hr_z2),
                "z3": _hr_band_payload(profile.hr_z3),
                "z4": _hr_band_payload(profile.hr_z4),
                "z5": _hr_band_payload(profile.hr_z5),
            }
            if profile.calibrated
            else None
        ),
        "pace_zones": pace_zones if pace_zones else None,
        "pace_source": profile.pace_source,
        "pace_computed_at": (
            profile.pace_computed_at.isoformat() if profile.pace_computed_at else None
        ),
        "insights_easy_banner": insights_easy_banner,
    }
