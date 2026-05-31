"""HR zone builder respects trusted max HR gate."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.runner_profile.hr_builder import compute_hr_zones


@patch("src.smartcoach_mobile_coach.runner_profile.hr_builder.get_user_profile")
@patch(
    "src.smartcoach_mobile_coach.runner_profile.hr_builder.HRMaxResolutionService.get_trusted_max_hr_for_zones"
)
def test_compute_hr_zones_returns_none_when_untrusted(mock_trusted, mock_profile):
    mock_profile.return_value = {
        "max_hr_auto": 161,
        "hrmax_confidence": "MEDIUM",
    }
    mock_trusted.return_value = None

    assert compute_hr_zones(MagicMock(), "user-1") is None


@patch("src.smartcoach_mobile_coach.runner_profile.hr_builder.get_user_profile")
@patch(
    "src.smartcoach_mobile_coach.runner_profile.hr_builder.HRMaxResolutionService.get_trusted_max_hr_for_zones"
)
def test_compute_hr_zones_computes_when_trusted(mock_trusted, mock_profile):
    mock_profile.return_value = {
        "max_hr_manual": 174,
        "resting_hr": None,
    }
    mock_trusted.return_value = 174

    result = compute_hr_zones(MagicMock(), "user-1")

    assert result is not None
    assert result.hrmax_used == 174
    assert result.method == "pct_max"
    assert result.zones["z2"].low == 104
    assert result.zones["z2"].high == 130
