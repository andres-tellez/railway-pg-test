import pytest
from flask.testing import FlaskClient
from src.app import app
from src.db.db_session import get_engine
from sqlalchemy import text
from unittest.mock import patch

client = app.test_client()
HEADERS = {"Origin": "http://localhost:5173"}


def base_payload():
    return {
        "user_id": "test-user-123",
        "trainingDays": ["Mon", "Wed", "Fri"],
        "trainingGoal": "Build endurance",
        "hasInjury": False,
        "injuryDetails": None,
        "runnerLevel": "Intermediate",
        "raceHistory": False,
        "raceDate": "2025-09-01",
        "raceDistance": "10K",
        "pastRaces": ["5K", "10K"],
        "height": {"feet": 5, "inches": 10},
        "weight": 165,
        "mainGoal": "Run a race",
        "motivation": ["Competition"],
        "ageGroup": "25-34",
        "longestRun": 10,
        "runPreference": "Distance",
        "trainingDaysPerWeek": 3,
    }


@patch("flask_jwt_extended.utils.get_jwt", return_value={"sub": "test-user-123"})
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request", return_value=None)
def test_onboarding_success(_, __):
    payload = base_payload()
    response = client.post("/api/onboarding", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "Profile saved successfully"

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM user_profile WHERE user_id = 'test-user-123'")
        )
        row = result.fetchone()
        assert row is not None


@patch("flask_jwt_extended.utils.get_jwt", return_value={"sub": "test-user-123"})
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request", return_value=None)
def test_missing_required_field(_, __):
    payload = base_payload()
    payload.pop("runnerLevel")
    response = client.post("/api/onboarding", json=payload, headers=HEADERS)
    assert response.status_code == 400
    assert "errors" in response.get_json()


@patch("flask_jwt_extended.utils.get_jwt", return_value={"sub": "test-user-123"})
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request", return_value=None)
def test_invalid_enum_value(_, __):
    payload = base_payload()
    payload["ageGroup"] = "OldMan"
    response = client.post("/api/onboarding", json=payload, headers=HEADERS)
    assert response.status_code == 400
    assert "errors" in response.get_json()


@patch("flask_jwt_extended.utils.get_jwt", return_value={"sub": "test-user-123"})
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request", return_value=None)
def test_wrong_data_type(_, __):
    payload = base_payload()
    payload["height"]["inches"] = "ten"
    response = client.post("/api/onboarding", json=payload, headers=HEADERS)
    assert response.status_code == 400
    assert "errors" in response.get_json()


@patch("flask_jwt_extended.utils.get_jwt", return_value={"sub": "test-user-123"})
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request", return_value=None)
def test_invalid_enum_in_array(_, __):
    payload = base_payload()
    payload["pastRaces"] = ["Potato"]
    response = client.post("/api/onboarding", json=payload, headers=HEADERS)
    assert response.status_code == 400
    assert "errors" in response.get_json()


@patch("flask_jwt_extended.utils.get_jwt", return_value={"sub": "test-user-123"})
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request", return_value=None)
def test_duplicate_submission_upserts(_, __):
    payload = base_payload()
    response1 = client.post("/api/onboarding", json=payload, headers=HEADERS)
    assert response1.status_code == 200

    # Modify payload (simulate updated user input)
    payload["longestRun"] = 15
    response2 = client.post("/api/onboarding", json=payload, headers=HEADERS)
    assert response2.status_code == 200

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT longest_run FROM user_profile WHERE user_id = 'test-user-123'")
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == 15  # Confirm it was updated
