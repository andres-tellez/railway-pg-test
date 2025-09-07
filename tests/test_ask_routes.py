import pytest
from flask import Flask
from src.routes.ask_routes import ask_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(ask_bp)
    app.config["TESTING"] = True
    return app.test_client()


def test_valid_request(client):
    response = client.post(
        "/ask", json={"question": " How far did I run today? ", "athlete_id": 123}
    )
    assert response.status_code in (200, 302)
    data = response.get_json()
    assert data["athlete_id"] == 123
    assert data["question"] == "How far did I run today?"


def test_missing_content_type(client):
    response = client.post("/ask", data="invalid", content_type="text/plain")
    assert response.status_code == 400
    assert "content-type" in response.get_json()["error"]


def test_missing_payload(client):
    response = client.post("/ask", json=None)
    assert response.status_code == 400
    assert (
        "content-type must be application/json" in response.get_json()["error"].lower()
    )


def test_invalid_question(client):
    response = client.post("/ask", json={"question": "   ", "athlete_id": 1})
    assert response.status_code == 400
    assert "question" in response.get_json()["error"]


def test_missing_athlete_id(client):
    response = client.post("/ask", json={"question": "What's my progress?"})
    assert response.status_code == 400
    assert "athlete_id" in response.get_json()["error"]


def test_invalid_athlete_id(client):
    response = client.post("/ask", json={"question": "Status?", "athlete_id": -5})
    assert response.status_code == 400
    assert "athlete_id" in response.get_json()["error"]
