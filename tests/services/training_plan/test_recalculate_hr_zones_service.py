"""Tests for plan workout HR recalc after profile max-HR changes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services.training_plan.recalculate_hr_zones_service import (
    recalculate_hr_zones_for_user,
)


def test_recalculate_hr_zones_for_user_refreshes_runner_profile_before_plan_recalc():
    session = MagicMock()
    plan = MagicMock()
    plan.id = 42
    session.query.return_value.filter_by.return_value.all.return_value = [plan]

    with patch(
        "src.smartcoach_mobile_coach.runner_profile.refresh_runner_profile"
    ) as refresh_mock, patch(
        "src.services.training_plan.recalculate_hr_zones_service.recalculate_hr_zones_for_plan",
        return_value={"updated": 3, "skipped": 0, "errors": 0},
    ) as plan_recalc_mock:
        results = recalculate_hr_zones_for_user(session, "user-123")

    refresh_mock.assert_called_once_with(session, "user-123")
    plan_recalc_mock.assert_called_once_with(session, 42)
    assert results[42]["updated"] == 3
