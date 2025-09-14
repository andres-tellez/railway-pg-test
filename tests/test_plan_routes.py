# tests/test_plan_routes.py

import uuid
import pytest
import json
from unittest.mock import patch
from flask import g

from src.db.models.user_identity import UserIdentity
from src.db.models.plans import Plan


def fake_call_gpt_valid(prompt: str) -> str:
    """Fake GPT response that passes validation."""
    return json.dumps(
        {
            "plan_name": "Mock Plan",
            "notes": "This is a test plan",
            "workouts": [
                {
                    "date": "2025-09-20",
                    "workout_type": "Easy",
                    "description": "3 miles easy run",
                    "miles": 3.0,
                    "intensity": "Easy",
                },
                {
                    "date": "2025-09-21",
                    "workout_type": "Rest",
                    "description": "Rest day",
                    "miles": 0.0,
                    "intensity": "Easy",
                },
            ],
        }
    )


@pytest.mark.usefixtures("client", "test_db_session")
def test_generate_plan_with_real_user(client, test_db_session):
    user_id = uuid.uuid4()
    test_db_session.add(UserIdentity(user_id=user_id, email="real@example.com"))
    test_db_session.commit()

    with patch(
        "src.services.training_plan_service.call_gpt", side_effect=fake_call_gpt_valid
    ):
        response = client.post(
            "/api/plan/generate",
            json={
                "user_id": str(user_id),
                "race_date": "2025-12-01",
                "race_distance": "Marathon",
            },
        )

    assert response.status_code == 201
    data = response.get_json()
    assert "plan_id" in data
    assert isinstance(data["plan_id"], int)


@pytest.mark.usefixtures("client", "test_db_session")
def test_generate_plan_missing_user_returns_404(client):
    random_user_id = uuid.uuid4()

    with patch(
        "src.services.training_plan_service.call_gpt", side_effect=fake_call_gpt_valid
    ):
        response = client.post(
            "/api/plan/generate",
            json={
                "user_id": str(random_user_id),
                "race_date": "2025-12-01",
                "race_distance": "5K",
            },
        )

    assert response.status_code == 404
    assert response.get_json()["error"] == "User not found"


def test_get_plan_by_id_success(client, test_db_session):
    user_id = uuid.uuid4()
    test_user = UserIdentity(user_id=user_id, email="user@example.com")
    test_db_session.add(test_user)
    test_db_session.commit()

    with patch(
        "src.services.training_plan_service.call_gpt", side_effect=fake_call_gpt_valid
    ):
        response = client.post(
            "/api/plan/generate",
            json={
                "user_id": str(user_id),
                "race_date": "2025-12-15",
                "race_distance": "10K",
            },
        )

    assert response.status_code == 201
    plan_id = response.get_json()["plan_id"]

    # ✅ Simulate auth using header
    get_response = client.get(
        f"/api/plan/{plan_id}", headers={"X-User-Id": str(user_id)}
    )

    assert get_response.status_code == 200
    data = get_response.get_json()
    assert "plan" in data
    assert "workouts" in data
    assert len(data["workouts"]) == 2


def test_get_plan_by_id_unauthorized(client):
    # No X-User-Id header
    get_response = client.get("/api/plan/1")
    assert get_response.status_code == 401
    assert get_response.get_json()["error"] == "Unauthorized"


def test_get_plan_by_id_not_found(client):
    user_id = uuid.uuid4()
    get_response = client.get(
        "/api/plan/999999",  # Non-existent plan
        headers={"X-User-Id": str(user_id)},  # Valid simulated user
    )
    assert get_response.status_code == 404
    assert get_response.get_json()["error"] == "Plan not found"
