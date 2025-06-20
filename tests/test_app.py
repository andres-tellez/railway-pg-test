import pytest
from unittest.mock import patch, MagicMock
from src.app import create_app

@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client

def test_ping(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.data == b"pong"

@patch("sqlalchemy.inspect")
@patch("sqlalchemy.create_engine")
def test_db_check_success(mock_create_engine, mock_inspect, client):
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_insp = MagicMock()
    mock_inspect.return_value = mock_insp
    mock_insp.get_columns.return_value = [
        {"name": "id", "type": "Integer", "nullable": False},
        {"name": "split", "type": "Integer", "nullable": True}
    ]

    resp = client.get("/db-check")
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["status"] == "ok"
    assert json_data["split_column"]["name"] == "split"
    assert json_data["split_column"]["nullable"] is True

@patch("sqlalchemy.create_engine", side_effect=Exception("DB failure"))
def test_db_check_failure(mock_create_engine, client):
    resp = client.get("/db-check")
    assert resp.status_code == 500
    json_data = resp.get_json()
    assert json_data["status"] == "fail"
    assert "DB failure" in json_data["error"]

def test_startup(client):
    resp = client.get("/startup")
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert "status" in json_data and json_data["status"] == "started"
    assert "cwd" in json_data
    assert "files" in json_data

def test_blueprints_registered(client):
    # Test that known blueprint routes exist
    resp = client.get("/ping")
    assert resp.status_code == 200

    resp = client.get("/auth/login")
    # This route exists but may redirect or 405 if not POST; just check not 404
    assert resp.status_code != 404

    resp = client.get("/sync/enrich/status")
    assert resp.status_code == 200
