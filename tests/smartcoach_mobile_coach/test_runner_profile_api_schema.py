"""Runner profile JSON payload shape for mobile clients."""

from __future__ import annotations

from datetime import datetime, timezone

from src.smartcoach_mobile_coach.runner_profile.api_schema import (
    INSIGHTS_EASY_BANNER_SUBTITLE,
    runner_zone_profile_payload,
)
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)


def test_pace_zones_partial_includes_only_present_bands_and_preserves_banner():
    """pace_zones must expose z2 even when z3/z4 pace columns are absent."""
    hr_z2 = HrZoneBand(low=120, high=145)
    pace_z2 = PaceZoneBand(
        low_sec=600,
        high_sec=630,
        display="10:00-10:30/mi",
    )
    profile = RunnerZoneProfileData(
        user_id="u",
        calibrated=True,
        computed_at=datetime.now(timezone.utc),
        hrmax_used=185,
        resting_hr_used=50,
        zone_method="karvonen",
        hr_z1=HrZoneBand(100, 115),
        hr_z2=hr_z2,
        hr_z3=HrZoneBand(146, 160),
        hr_z4=HrZoneBand(161, 175),
        hr_z5=HrZoneBand(176, 185),
        pace_z2=pace_z2,
        pace_z3=None,
        pace_z4=None,
        pace_source="calibration",
        pace_computed_at=datetime.now(timezone.utc),
    )
    payload = runner_zone_profile_payload(profile)
    pz = payload["pace_zones"]
    assert pz is not None
    assert set(pz.keys()) == {"z2"}
    assert pz["z2"]["display"] == pace_z2.display

    banner = payload.get("insights_easy_banner")
    assert banner is not None
    assert banner["subtitle"] == INSIGHTS_EASY_BANNER_SUBTITLE
