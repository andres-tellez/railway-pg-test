"""Phase 0 smoke checks: pct_max fallback, no silent resting HR writes, manual save + recalc."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from src.app import app
from src.db.dao.user_profile_dao import get_user_profile, save_user_profile
from src.services.heart_rate.heart_rate_orchestration_service import (
    HeartRateZoneOrchestrationService,
)
from src.smartcoach_mobile_coach.runner_profile.hr_builder import compute_hr_zones

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID_STR = str(DEFAULT_USER_ID)

client = app.test_client()
HEADERS = {
    "Origin": "http://localhost:5173",
    "Authorization": "Bearer fake-token",
}


@pytest.fixture(autouse=True)
def stub_auth_user_id(monkeypatch):
    monkeypatch.setattr(
        "src.utils.auth0_jwt.resolve_user_id_from_auth_provider",
        lambda *args, **kwargs: DEFAULT_USER_ID,
    )


def _profile(**overrides):
    profile = {
        "user_id": DEFAULT_USER_ID_STR,
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


def _onboarding_base_payload(**overrides):
    payload = {
        "user_id": DEFAULT_USER_ID_STR,
        "height": {"feet": 5, "inches": 10},
        "weight": 165,
        "ageGroup": "25-34",
        "max_hr_manual": 180,
        "max_hr_active": "manual",
    }
    payload.update(overrides)
    return payload


class TestPhase0SmokePctMaxFallback:
    def test_zones_compute_via_pct_max_without_resting_hr(self, test_db_session):
        save_user_profile(test_db_session, _profile())

        zones = compute_hr_zones(test_db_session, DEFAULT_USER_ID_STR)
        assert zones is not None
        assert zones.method == "pct_max"
        assert zones.resting_hr_used is None
        assert zones.hrmax_used == 180
        assert "z2" in zones.zones

    def test_calculate_zones_e2e_leaves_profile_resting_hr_null(self, test_db_session):
        save_user_profile(test_db_session, _profile())

        with patch(
            "src.smartcoach_mobile_coach.runner_profile.service.compute_pace_zones_from_activities",
            return_value=None,
        ):
            result = HeartRateZoneOrchestrationService.calculate_zones_for_user(
                test_db_session, DEFAULT_USER_ID_STR
            )

        assert result["success"] is True
        assert result.get("zones")
        assert result.get("resting_hr") is None

        profile = get_user_profile(test_db_session, DEFAULT_USER_ID_STR)
        assert profile["resting_hr"] is None
        assert profile.get("resting_hr_source") is None


class TestPhase0SmokeOnboardingManualSave:
    def test_manual_resting_hr_save_sets_user_source(self, test_db_session):
        save_user_profile(test_db_session, _profile())

        response = client.post(
            "/api/onboarding",
            json=_onboarding_base_payload(restingHr=55),
            headers=HEADERS,
        )
        assert response.status_code == 200

        profile = get_user_profile(test_db_session, DEFAULT_USER_ID_STR)
        assert profile["resting_hr"] == 55
        assert profile["resting_hr_source"] == "USER"
        assert profile["resting_hr_updated_at"] is not None

    def test_resting_hr_change_triggers_hr_zone_recalc(self, test_db_session):
        save_user_profile(test_db_session, _profile())

        with patch(
            "src.services.training_plan.recalculate_hr_zones_service.recalculate_hr_zones_for_user",
            return_value={},
        ) as recalc_mock:
            response = client.post(
                "/api/onboarding",
                json=_onboarding_base_payload(restingHr=58),
                headers=HEADERS,
            )

        assert response.status_code == 200
        recalc_mock.assert_called_once()
        call_args = recalc_mock.call_args[0]
        assert str(call_args[1]) == DEFAULT_USER_ID_STR
