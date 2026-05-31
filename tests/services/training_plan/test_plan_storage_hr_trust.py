"""Plan save keeps pace targets when HR zones are not zone-trusted."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services.training_plan.plan_storage_service import PlanStorageService


@patch(
    "src.services.training_plan.plan_storage_service.PlanStorageService._calculate_hr_zone"
)
@patch(
    "src.services.training_plan.plan_storage_service.get_runner_pace_band_for_run_type"
)
@patch("src.smartcoach_mobile_coach.runner_profile.get_runner_profile")
def test_workout_row_empty_target_hr_when_zones_uncalibrated(
    mock_get_profile, mock_pace_band, mock_hr_zone
):
    mock_get_profile.return_value = MagicMock(calibrated=False, pace_z2=None)
    mock_pace_band.return_value = (540, 600)
    mock_hr_zone.return_value = ""

    row = PlanStorageService._workout_to_row(
        plan_id=1,
        date=MagicMock(),
        phase="Base",
        run={"type": "easy", "label": "Easy", "miles": 5.0},
        details={"segments": {}, "cues": "Easy run"},
        user_profile={},
        session=MagicMock(),
        user_id="user-1",
    )

    assert row["target_hr"] == ""
    assert row["target_zone"] != ""
