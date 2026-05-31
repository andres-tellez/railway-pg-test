"""Resting HR is never age-estimated or silently persisted (Phase 0)."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.db.dao.user_profile_dao import get_user_profile, save_user_profile
from src.services.heart_rate.heart_rate_orchestration_service import (
    HeartRateZoneOrchestrationService,
)
from src.smartcoach_mobile_coach.runner_profile.hr_builder import compute_hr_zones
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    RunnerZoneProfileData,
)


@pytest.fixture
def user_id() -> str:
    return str(uuid.uuid4())


def _base_profile(uid: str, **overrides):
    profile = {
        "user_id": uid,
        "height_feet": 5,
        "height_inches": 10,
        "max_hr_manual": 180,
        "max_hr_active": "manual",
        "age_group": "25-34",
        "resting_hr": None,
        "resting_hr_source": None,
    }
    profile.update(overrides)
    return profile


def _runner_profile(uid: str, *, resting_hr_used: int | None = None, hrmax: int = 180):
    return RunnerZoneProfileData(
        user_id=uid,
        calibrated=True,
        computed_at=datetime.utcnow(),
        hrmax_used=hrmax,
        resting_hr_used=resting_hr_used,
        zone_method="karvonen" if resting_hr_used else "pct_max",
        hr_z1=HrZoneBand(90, 108),
        hr_z2=HrZoneBand(108, 126),
        hr_z3=HrZoneBand(126, 144),
        hr_z4=HrZoneBand(144, 162),
        hr_z5=HrZoneBand(162, 180),
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
    )


class TestCalculateZonesNoRestingHrEstimation:
    def test_missing_resting_hr_stays_null_after_zone_calc(
        self, test_db_session, user_id
    ):
        save_user_profile(test_db_session, _base_profile(user_id))

        with patch(
            "src.services.heart_rate.heart_rate_orchestration_service.refresh_runner_profile",
            return_value=_runner_profile(user_id),
        ):
            result = HeartRateZoneOrchestrationService.calculate_zones_for_user(
                test_db_session, user_id
            )

        assert result["success"] is True
        profile = get_user_profile(test_db_session, user_id)
        assert profile["resting_hr"] is None
        assert profile.get("resting_hr_source") is None

    def test_calculate_zones_never_persists_estimated_resting_hr(
        self, test_db_session, user_id
    ):
        save_user_profile(test_db_session, _base_profile(user_id))
        save_calls: list[dict] = []
        original_save = save_user_profile

        def track_save(session, data):
            save_calls.append(dict(data))
            return original_save(session, data)

        with patch(
            "src.services.heart_rate.heart_rate_orchestration_service.save_user_profile",
            side_effect=track_save,
        ), patch(
            "src.services.heart_rate.heart_rate_orchestration_service.refresh_runner_profile",
            return_value=_runner_profile(user_id),
        ):
            HeartRateZoneOrchestrationService.calculate_zones_for_user(
                test_db_session, user_id
            )

        for payload in save_calls:
            assert payload.get("resting_hr_source") != "ESTIMATED"
            assert "resting_hr" not in payload or payload.get("resting_hr") is None

    def test_manual_resting_hr_preserved_after_zone_calc(
        self, test_db_session, user_id
    ):
        save_user_profile(
            test_db_session,
            _base_profile(user_id, resting_hr=58, resting_hr_source="USER"),
        )

        with patch(
            "src.services.heart_rate.heart_rate_orchestration_service.refresh_runner_profile",
            return_value=_runner_profile(user_id, resting_hr_used=58),
        ):
            result = HeartRateZoneOrchestrationService.calculate_zones_for_user(
                test_db_session, user_id
            )

        assert result["success"] is True
        assert result["resting_hr"] == 58
        assert result["resting_hr_source"] == "USER"
        profile = get_user_profile(test_db_session, user_id)
        assert profile["resting_hr"] == 58
        assert profile["resting_hr_source"] == "USER"


class TestHrZoneStatusNoRestingHrEstimation:
    def test_status_ready_with_pct_max_when_max_hr_without_resting_hr(
        self, test_db_session, user_id
    ):
        save_user_profile(test_db_session, _base_profile(user_id))

        with patch(
            "src.services.heart_rate.heart_rate_orchestration_service.get_by_user_id",
            return_value=Mock(),
        ):
            status = HeartRateZoneOrchestrationService.get_hr_zone_status(
                test_db_session, user_id
            )

        assert status["ready"] is True
        assert status["method"] == "SIMPLE_PERCENTAGE"
        assert status["accuracy_tier"] == "LOW"
        assert status["readiness"]["can_estimate_resting_hr"] is False
        assert status["readiness"]["resting_hr_reason"] == "not_set"
        assert status["next_action"] == "add_resting_hr"
        assert "resting_hr_missing" not in status["issues"]


class TestManualRestingHrSource:
    def test_manual_save_sets_user_source(self, test_db_session, user_id):
        save_user_profile(test_db_session, _base_profile(user_id))

        profile = get_user_profile(test_db_session, user_id)
        profile["resting_hr"] = 55
        profile["resting_hr_source"] = "USER"
        profile["resting_hr_updated_at"] = datetime.now()
        save_user_profile(test_db_session, profile)

        updated = get_user_profile(test_db_session, user_id)
        assert updated["resting_hr"] == 55
        assert updated["resting_hr_source"] == "USER"
        assert updated["resting_hr_updated_at"] is not None


class TestPctMaxFallbackZones:
    def test_compute_hr_zones_without_resting_hr(self, test_db_session, user_id):
        save_user_profile(test_db_session, _base_profile(user_id))

        result = compute_hr_zones(test_db_session, user_id)

        assert result is not None
        assert result.method == "pct_max"
        assert result.resting_hr_used is None
        assert result.hrmax_used == 180
        assert "z2" in result.zones
