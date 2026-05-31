"""Tests for resting HR source on onboarding/profile save (Phase 1 backend)."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import patch

import pytest

from src.app import app
from src.db.dao.user_profile_dao import get_user_profile, save_user_profile
from src.utils.resting_hr_source import resolve_resting_hr_source_for_save

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


class TestResolveRestingHrSourceHelper:
    def test_apple_health_requires_explicit_resting_hr(self):
        assert (
            resolve_resting_hr_source_for_save(
                raw_body={"restingHr": 55, "restingHrSource": "APPLE_HEALTH"},
                requested_source="APPLE_HEALTH",
                new_resting_hr=55,
            )
            == "APPLE_HEALTH"
        )
        assert (
            resolve_resting_hr_source_for_save(
                raw_body={"restingHrSource": "APPLE_HEALTH"},
                requested_source="APPLE_HEALTH",
                new_resting_hr=55,
            )
            is None
        )

    def test_invalid_source_defaults_to_user(self):
        assert (
            resolve_resting_hr_source_for_save(
                raw_body={"restingHr": 55, "restingHrSource": "ESTIMATED"},
                requested_source="ESTIMATED",
                new_resting_hr=55,
            )
            == "USER"
        )


class TestRestingHrSourceOnboardingSave:
    def test_apple_health_source_persists(self, test_db_session):
        save_user_profile(test_db_session, _profile())

        response = client.post(
            "/api/onboarding",
            json=_onboarding_base_payload(restingHr=54, restingHrSource="APPLE_HEALTH"),
            headers=HEADERS,
        )
        assert response.status_code == 200

        profile = get_user_profile(test_db_session, DEFAULT_USER_ID_STR)
        assert profile["resting_hr"] == 54
        assert profile["resting_hr_source"] == "APPLE_HEALTH"

    def test_apple_health_accepts_snake_case_fields(self, test_db_session):
        save_user_profile(test_db_session, _profile())

        response = client.post(
            "/api/onboarding",
            json=_onboarding_base_payload(
                resting_hr=53, resting_hr_source="APPLE_HEALTH"
            ),
            headers=HEADERS,
        )
        assert response.status_code == 200

        profile = get_user_profile(test_db_session, DEFAULT_USER_ID_STR)
        assert profile["resting_hr"] == 53
        assert profile["resting_hr_source"] == "APPLE_HEALTH"

    def test_manual_save_sets_user_source(self, test_db_session):
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

    def test_manual_save_after_apple_health_overrides_source(self, test_db_session):
        save_user_profile(
            test_db_session,
            _profile(
                resting_hr=55,
                resting_hr_source="APPLE_HEALTH",
                resting_hr_updated_at=datetime.now(),
            ),
        )

        response = client.post(
            "/api/onboarding",
            json=_onboarding_base_payload(restingHr=55),
            headers=HEADERS,
        )
        assert response.status_code == 200

        profile = get_user_profile(test_db_session, DEFAULT_USER_ID_STR)
        assert profile["resting_hr"] == 55
        assert profile["resting_hr_source"] == "USER"

    def test_invalid_source_rejected_and_not_persisted(self, test_db_session):
        save_user_profile(test_db_session, _profile())

        response = client.post(
            "/api/onboarding",
            json=_onboarding_base_payload(restingHr=55, restingHrSource="ESTIMATED"),
            headers=HEADERS,
        )
        assert response.status_code == 400

        profile = get_user_profile(test_db_session, DEFAULT_USER_ID_STR)
        assert profile["resting_hr"] is None
        assert profile.get("resting_hr_source") is None

    def test_resting_hr_change_triggers_recalc(self, test_db_session):
        save_user_profile(test_db_session, _profile())

        with patch(
            "src.services.training_plan.recalculate_hr_zones_service.recalculate_hr_zones_for_user",
            return_value={},
        ) as recalc_mock:
            response = client.post(
                "/api/onboarding",
                json=_onboarding_base_payload(
                    restingHr=58, restingHrSource="APPLE_HEALTH"
                ),
                headers=HEADERS,
            )

        assert response.status_code == 200
        recalc_mock.assert_called_once()
