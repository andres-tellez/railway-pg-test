"""
Smoke tests: non-overlapping HR zone ownership flows through API, plan strings, and Coach.

Profile mobile, plan target_hr, and Coach/LLM context all read ``runner_zone_profiles``
``low/high`` via ``get_runner_profile`` / ``runner_zone_profile_payload`` /
``get_runner_zone_string_for_run_type`` / ``fetch_user_hr_profile_for_coach`` — no
separate display layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.db_helpers import fetch_user_hr_profile_for_coach
from src.smartcoach_mobile_coach.execution_analytics.kpi_primitives import (
    compute_split_kpis,
)
from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import (
    TempoHrZoneBounds,
    TempoSplitRow,
    _classify_split_hr,
)
from src.smartcoach_mobile_coach.runner_profile.api_schema import (
    runner_zone_profile_payload,
)
from src.smartcoach_mobile_coach.runner_profile.hr_builder import (
    apply_integer_zone_ownership,
    compute_hr_zones,
)
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    HrZoneComputation,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_core import (
    classify_hr_corridor_progress,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_easy import (
    classify_easy_hr_progress,
)
from src.smartcoach_mobile_coach.runner_profile.service import (
    get_runner_zone_string_for_run_type,
)
from src.smartcoach_mobile_coach.runner_profile.training_target_context import (
    _profile_hr_zones_payload,
)

from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_tempo import (
    DEFAULT_HR_PROGRESS_TEMPO_CONFIG,
)

_ZONE_KEYS = ("z1", "z2", "z3", "z4", "z5")


def _assert_adjacent_bands_non_overlapping(hr_zones: dict) -> None:
    ordered = [hr_zones[k] for k in _ZONE_KEYS if k in hr_zones and hr_zones[k]]
    for lower, upper in zip(ordered, ordered[1:]):
        assert lower["high"] < upper["low"], f"adjacent overlap: {lower} then {upper}"


def _owned_profile_from_pre_rounded_overlap() -> RunnerZoneProfileData:
    """Example overlap after Karvonen rounding: Z2 123–142, Z3 142–155."""
    owned = apply_integer_zone_ownership(
        {
            "z1": HrZoneBand(90, 109),
            "z2": HrZoneBand(123, 142),
            "z3": HrZoneBand(142, 155),
            "z4": HrZoneBand(155, 168),
            "z5": HrZoneBand(168, 174),
        }
    )
    return RunnerZoneProfileData(
        user_id="user-smoke",
        calibrated=True,
        computed_at=datetime.now(timezone.utc),
        hrmax_used=174,
        resting_hr_used=50,
        zone_method="karvonen",
        hr_z1=owned["z1"],
        hr_z2=owned["z2"],
        hr_z3=owned["z3"],
        hr_z4=owned["z4"],
        hr_z5=owned["z5"],
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
    )


@patch("src.smartcoach_mobile_coach.runner_profile.hr_builder.get_user_profile")
@patch(
    "src.smartcoach_mobile_coach.runner_profile.hr_builder.HRMaxResolutionService.get_trusted_max_hr_for_zones"
)
def test_compute_hr_zones_returns_non_overlapping_bands(mock_trusted, mock_profile):
    mock_profile.return_value = {
        "max_hr_manual": 174,
        "resting_hr": 50,
    }
    mock_trusted.return_value = 174

    result = compute_hr_zones(MagicMock(), "user-1")

    assert result is not None
    assert result.method == "karvonen"
    ordered = [result.zones[k] for k in _ZONE_KEYS if k in result.zones]
    for lower, upper in zip(ordered, ordered[1:]):
        assert lower.high < upper.low


def test_api_payload_plan_strings_and_coach_share_owned_bands():
    profile = _owned_profile_from_pre_rounded_overlap()

    api_zones = runner_zone_profile_payload(profile)["hr_zones"]
    _assert_adjacent_bands_non_overlapping(api_zones)
    assert api_zones["z2"] == {"low": 123, "high": 142}
    assert api_zones["z3"] == {"low": 143, "high": 155}

    coach_zones = _profile_hr_zones_payload(profile)
    assert coach_zones["z2"] == api_zones["z2"]
    assert coach_zones["z3"] == api_zones["z3"]

    session = MagicMock()
    with patch(
        "src.smartcoach_mobile_coach.runner_profile.service.get_runner_profile",
        return_value=profile,
    ):
        plan_z2 = get_runner_zone_string_for_run_type(session, profile.user_id, "easy")
        plan_z3 = get_runner_zone_string_for_run_type(session, profile.user_id, "tempo")

    assert plan_z2 == "Z2 (123–142 bpm)"
    assert plan_z3 == "Z3 (143–155 bpm)"

    uid = uuid.uuid4()
    row = MagicMock(
        zone_method="karvonen",
        hrmax_used=174.0,
        resting_hr_used=50.0,
        hr_z1_low=90,
        hr_z1_high=109,
        hr_z2_low=123,
        hr_z2_high=142,
        hr_z3_low=143,
        hr_z3_high=155,
        hr_z4_low=156,
        hr_z4_high=168,
        hr_z5_low=169,
        hr_z5_high=174,
        computed_at=datetime.now(timezone.utc),
    )
    session.query.return_value.filter.return_value.first.return_value = row
    coach_profile = fetch_user_hr_profile_for_coach(session, str(uid))

    assert coach_profile is not None
    assert coach_profile["zones_bpm"]["z2"] == {"low": 123.0, "high": 142.0}
    assert coach_profile["zones_bpm"]["z3"] == {"low": 143.0, "high": 155.0}


def test_boundary_bpm_ownership_is_deterministic():
    profile = _owned_profile_from_pre_rounded_overlap()
    z2 = profile.hr_z2
    z3 = profile.hr_z3
    assert z2 is not None and z3 is not None

    shared_boundary = 142
    upper_start = 143

    assert z2.low <= shared_boundary <= z2.high
    assert not (z3.low <= shared_boundary <= z3.high)
    assert z3.low <= upper_start <= z3.high
    assert z2.high + 1 == z3.low

    assert (
        classify_easy_hr_progress(avg_hr_bpm=float(shared_boundary), target_hr_z2=z2)
        == "green"
    )
    assert (
        classify_easy_hr_progress(avg_hr_bpm=float(upper_start), target_hr_z2=z2)
        == "yellow"
    )

    gap_cfg = DEFAULT_HR_PROGRESS_TEMPO_CONFIG
    assert (
        classify_hr_corridor_progress(
            avg_hr_bpm=float(shared_boundary), corridor=z3, gap_cfg=gap_cfg
        )
        != "green"
    )
    assert (
        classify_hr_corridor_progress(
            avg_hr_bpm=float(upper_start), corridor=z3, gap_cfg=gap_cfg
        )
        == "green"
    )

    assert profile.hr_z4 is not None
    bounds = TempoHrZoneBounds(
        z2_high=float(z2.high),
        z3_low=float(z3.low),
        z3_high=float(z3.high),
        z4_low=float(profile.hr_z4.low),
    )
    assert _classify_split_hr(float(shared_boundary), bounds) != "z3"
    assert _classify_split_hr(float(upper_start), bounds) == "z3"

    kpis = compute_split_kpis(
        [
            TempoSplitRow(
                split_index=1,
                avg_hr=float(shared_boundary),
                pace_min_per_mi=9.0,
                distance_mi=1.0,
            ),
            TempoSplitRow(
                split_index=2,
                avg_hr=float(upper_start),
                pace_min_per_mi=8.5,
                distance_mi=1.0,
            ),
        ],
        z2_low=float(z2.low),
        z2_high=float(z2.high),
        z3_low=float(z3.low),
        z3_high=float(z3.high),
        z4_low=float(profile.hr_z4.low) if profile.hr_z4 else None,
    )
    assert kpis.z2_band_pct == 0.5
    assert kpis.n_z3_splits == 1


def test_persisted_hr_computation_matches_api_after_ownership():
    owned = apply_integer_zone_ownership(
        {
            "z2": HrZoneBand(123, 142),
            "z3": HrZoneBand(142, 155),
        }
    )
    hr = HrZoneComputation(
        zones=owned,
        method="karvonen",
        hrmax_used=174,
        resting_hr_used=50,
    )
    profile = RunnerZoneProfileData(
        user_id="u",
        calibrated=True,
        computed_at=datetime.now(timezone.utc),
        hrmax_used=174,
        resting_hr_used=50,
        zone_method="karvonen",
        hr_z1=None,
        hr_z2=owned["z2"],
        hr_z3=owned["z3"],
        hr_z4=None,
        hr_z5=None,
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
    )
    payload = runner_zone_profile_payload(profile)
    assert payload["hr_zones"]["z2"]["high"] == hr.zones["z2"].high
    assert payload["hr_zones"]["z3"]["low"] == hr.zones["z3"].low
