from src.routes.ask_routes import ask_bp
from flask import Flask
import pytest


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(ask_bp)
    app.config["TESTING"] = True
    return app.test_client()


def test_ask_endpoint_formats_prompt(monkeypatch, client):
    # Fake activity data
    mock_activities = [
        {"date": "2025-06-26", "distance_km": 7, "duration_min": 38},
        {"date": "2025-06-27", "distance_km": 5, "duration_min": 30},
    ]

    # Patch downstream prompt formatter if wired
    from src.utils import gpt_ops

    monkeypatch.setattr(
        gpt_ops, "format_prompt", lambda q, a: f"MOCK_PROMPT: {q} / {len(a)} activities"
    )

    response = client.post(
        "/ask", json={"question": "How much did I run?", "athlete_id": 10}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "question" in data
    assert data["question"].startswith("How much did I run?")
