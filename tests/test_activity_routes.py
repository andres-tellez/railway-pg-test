import os
import uuid

os.environ["FLASK_ENV"] = "test"
from unittest.mock import patch, MagicMock
import pytest

from src.routes.activity_routes import activity_bp

_RESOLVED_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_RESOLVED_USER_STR = str(_RESOLVED_USER_ID)


@pytest.fixture(autouse=True)
def _jwt_identity(monkeypatch):
    monkeypatch.setattr(
        "src.utils.auth0_jwt.resolve_user_id_from_auth_provider",
        lambda *args, **kwargs: _RESOLVED_USER_ID,
    )


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(activity_bp)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_enrich_status(client, auth_header):
    resp = client.get("/api/activities/enrich/status", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json == {"enrich": "ok"}


@patch("src.routes.activity_routes.get_session")
@patch("src.routes.activity_routes.ActivityIngestionService")
def test_enrich_single_activity_success(
    mock_service_cls, mock_get_session, client, auth_header
):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    # Simulate DB query returning athlete_id
    mock_session.execute.return_value.fetchone.return_value = MagicMock(athlete_id=123)
    mock_service = mock_service_cls.return_value
    mock_service.enrich_single_activity.return_value = True

    resp = client.post("/api/activities/enrich/activity/456", headers=auth_header())

    assert resp.status_code == 200
    assert resp.json.get("status") == "ok"

    mock_get_session.assert_called_once()
    mock_service_cls.assert_called_once_with(
        mock_session, 123, user_id=_RESOLVED_USER_STR
    )
    mock_service.enrich_single_activity.assert_called_once_with(456)
    mock_session.close.assert_called_once()


@patch("src.routes.activity_routes.get_session")
def test_enrich_single_activity_not_found(mock_get_session, client, auth_header):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    mock_session.execute.return_value.fetchone.return_value = None

    resp = client.post("/api/activities/enrich/activity/999", headers=auth_header())

    assert resp.status_code == 404
    assert "not found" in resp.json.get("error", "").lower()
    mock_session.close.assert_called_once()


@patch("src.routes.activity_routes.get_session")
@patch("src.routes.activity_routes.persist_splits_for_user", return_value=True)
@patch("src.routes.activity_routes.run_enrichment_batch")
def test_enrich_batch_success(
    mock_run_batch, mock_persist_splits, mock_get_session, client, auth_header
):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    mock_run_batch.return_value = 5

    resp = client.post(
        "/api/activities/enrich/batch?athlete_id=123&batch=10",
        headers=auth_header(),
    )

    assert resp.status_code == 200
    assert resp.json.get("enriched_count") == 5

    mock_persist_splits.assert_called_once_with(mock_session, _RESOLVED_USER_STR)
    mock_run_batch.assert_called_once_with(
        mock_session, 123, batch_size=10, persist_splits=True
    )
    mock_session.close.assert_called_once()


@patch("src.routes.activity_routes.get_session")
def test_enrich_batch_missing_athlete_id(mock_get_session, client, auth_header):
    resp = client.post("/api/activities/enrich/batch", headers=auth_header())

    assert resp.status_code == 400
    assert "missing athlete_id" in resp.json.get("error", "").lower()
    mock_get_session.assert_not_called()
