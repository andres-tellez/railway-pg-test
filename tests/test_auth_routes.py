import pytest
from unittest.mock import patch, MagicMock
from flask import url_for
import jwt
from datetime import datetime, timedelta
import src.utils.config as config
from src.routes.auth_routes import auth_bp

@pytest.fixture
def client():
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def create_jwt_token(sub="admin", exp=None):
    if exp is None:
        exp = datetime.utcnow() + timedelta(seconds=config.ACCESS_TOKEN_EXP)
    return jwt.encode({"sub": sub, "exp": exp}, config.SECRET_KEY, algorithm="HS256")

# --- /auth/login POST ---

def test_admin_login_success(client):
    data = {"username": config.ADMIN_USER, "password": config.ADMIN_PASS}
    response = client.post("/auth/login", json=data)
    assert response.status_code == 200
    assert "access_token" in response.json
    assert "refresh_token" in response.json

def test_admin_login_invalid_credentials(client):
    data = {"username": "wrong", "password": "wrong"}
    response = client.post("/auth/login", json=data)
    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized"

def test_admin_login_missing_json(client):
    response = client.post("/auth/login")
    assert response.status_code == 500 or response.status_code == 400

# --- /auth/login GET (Strava OAuth) ---

@patch("src.routes.auth_routes.get_authorization_url")
def test_strava_login_redirect(mock_get_auth_url, client):
    mock_get_auth_url.return_value = "http://fake-auth-url"
    response = client.get("/auth/login")
    assert response.status_code == 302
    assert response.location == "http://fake-auth-url"

# --- /auth/callback GET ---

@patch("src.routes.auth_routes.get_session")
@patch("src.routes.auth_routes.store_tokens_from_callback")
def test_callback_success(mock_store_tokens, mock_get_session, client):
    mock_store_tokens.return_value = 123
    mock_get_session.return_value = MagicMock()
    response = client.get("/auth/callback?code=fakecode")
    assert response.status_code == 200
    assert "Token stored for athlete_id: 123" in response.get_data(as_text=True)

def test_callback_missing_code(client):
    response = client.get("/auth/callback")
    assert response.status_code == 400
    assert "Missing OAuth code" in response.get_data(as_text=True)

@patch("src.routes.auth_routes.get_session")
@patch("src.routes.auth_routes.store_tokens_from_callback", side_effect=Exception("fail"))
def test_callback_exception(mock_store, mock_session, client):
    mock_session.return_value = MagicMock()
    response = client.get("/auth/callback?code=code")
    assert response.status_code == 500
    assert "Callback error" in response.get_data(as_text=True)

# --- /auth/refresh/<athlete_id> POST ---

@patch("src.routes.auth_routes.get_session")
@patch("src.routes.auth_routes.refresh_token_if_expired")
def test_refresh_token_success(mock_refresh, mock_get_session, client):
    mock_refresh.return_value = True
    mock_get_session.return_value = MagicMock()
    token = create_jwt_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/auth/refresh/1", headers=headers)
    assert response.status_code == 200
    assert response.json == {"refreshed": True}

def test_refresh_token_missing_auth_header(client):
    response = client.post("/auth/refresh/1")
    assert response.status_code == 401
    assert "Missing or invalid Authorization header" in response.json["error"]

def test_refresh_token_invalid_token(client):
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.post("/auth/refresh/1", headers=headers)
    assert response.status_code == 401
    assert response.json["error"] == "Invalid token"

# --- /auth/logout/<athlete_id> POST ---

@patch("src.routes.auth_routes.get_session")
@patch("src.routes.auth_routes.delete_athlete_tokens")
def test_logout_success(mock_delete, mock_get_session, client):
    mock_delete.return_value = True
    mock_get_session.return_value = MagicMock()
    response = client.post("/auth/logout/1")
    assert response.status_code == 200
    assert response.json == {"deleted": True}

# --- /auth/monitor-tokens GET ---

@patch("src.routes.auth_routes.get_session")
def test_monitor_tokens_success(mock_get_session, client):
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = [
        MagicMock(athlete_id=1, expires_at=123456789),
        MagicMock(athlete_id=2, expires_at=987654321)
    ]
    mock_get_session.return_value = mock_session

    response = client.get("/auth/monitor-tokens")
    assert response.status_code == 200
    assert isinstance(response.json, list)
    assert response.json[0]["athlete_id"] == 1

@patch("src.routes.auth_routes.get_session")
def test_monitor_tokens_exception(mock_get_session, client):
    mock_session = MagicMock()
    mock_session.execute.side_effect = Exception("DB fail")
    mock_get_session.return_value = mock_session

    response = client.get("/auth/monitor-tokens")
    assert response.status_code == 500
    assert "error" in response.json
