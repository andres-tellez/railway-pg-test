import os

os.environ["FLASK_ENV"] = "test"
from unittest.mock import patch, MagicMock
import pytest

from src.routes.activity_routes import activity_bp


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(activity_bp)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_enrich_status(client):
    resp = client.get("/enrich/status")
    assert resp.status_code == 200
    assert resp.json == {"enrich": "ok"}


@patch("src.routes.activity_routes.get_session")
@patch("src.routes.activity_routes.ActivityIngestionService")
def test_enrich_single_activity_success(mock_service_cls, mock_get_session, client):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    # Simulate DB query returning athlete_id
    mock_session.execute.return_value.fetchone.return_value = MagicMock(athlete_id=123)
    mock_service = mock_service_cls.return_value
    mock_service.enrich_single_activity.return_value = True

    resp = client.post("/enrich/activity/456")

    assert resp.status_code == 200
    assert resp.json.get("status") == "ok"

    mock_get_session.assert_called_once()
    mock_service_cls.assert_called_once_with(mock_session, 123)
    mock_service.enrich_single_activity.assert_called_once_with(456)
    mock_session.close.assert_called_once()


@patch("src.routes.activity_routes.get_session")
def test_enrich_single_activity_not_found(mock_get_session, client):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    mock_session.execute.return_value.fetchone.return_value = None

    resp = client.post("/enrich/activity/999")

    assert resp.status_code == 404
    assert "not found" in resp.json.get("error", "").lower()
    mock_session.close.assert_called_once()


@patch("src.routes.activity_routes.get_session")
@patch("src.routes.activity_routes.run_enrichment_batch")
def test_enrich_batch_success(mock_run_batch, mock_get_session, client):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    mock_run_batch.return_value = 5

    resp = client.post("/enrich/batch?athlete_id=123&batch=10")

    assert resp.status_code == 200
    assert resp.json.get("enriched_count") == 5

    mock_run_batch.assert_called_once_with(mock_session, 123, batch_size=10)
    mock_session.close.assert_called_once()


@patch("src.routes.activity_routes.get_session")
def test_enrich_batch_missing_athlete_id(mock_get_session, client):
    resp = client.post("/enrich/batch")

    assert resp.status_code == 400
    assert "missing athlete_id" in resp.json.get("error", "").lower()
    mock_get_session.assert_not_called()
