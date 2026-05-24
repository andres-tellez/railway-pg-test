"""Guards ensuring HR-only DB rows trigger pace recomputation."""

from __future__ import annotations

from datetime import datetime, timezone

from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.service import (
    _profile_needs_pace_repair,
)


def _sample_hr_calibrated_profile(*, pace_z2=None):
    hr_z2 = HrZoneBand(low=120, high=145)
    return RunnerZoneProfileData(
        user_id="x",
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
        pace_computed_at=None,
    )


def test_profile_needs_pace_repair_when_calibrated_but_no_z2_pace():
    assert (
        _profile_needs_pace_repair(_sample_hr_calibrated_profile(pace_z2=None)) is True
    )


def test_profile_does_not_need_repair_when_pace_z2_present():
    pace = PaceZoneBand(low_sec=600, high_sec=630, display="10:00-10:05/mi")
    assert (
        _profile_needs_pace_repair(_sample_hr_calibrated_profile(pace_z2=pace)) is False
    )
