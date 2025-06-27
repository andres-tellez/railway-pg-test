import os
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch
import src.utils.config as config  # Import config for admin credentials


@patch("src.services.token_service.refresh_token_static")
def test_login_refresh_logout(mock_refresh, client):
    """Test successful login, token refresh using Authorization header, and logout."""
    mock_refresh.return_value = {
        "access_token": "mocked_access",
        "refresh_token": "mocked_refresh",
        "expires_at": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    }

    # Step 1: Login with correct credentials from config
    resp = client.post("/auth/login", json={"username": config.ADMIN_USER, "password": config.ADMIN_PASS})
    assert resp.status_code == 200

    tokens = resp.get_json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # 🔧 Inject mock token record into DB for athlete_id=0
    from src.db.models.tokens import Token
    from src.db.db_session import get_session
    session = get_session()

    with session as db_session:
        db_session.add(Token(
            athlete_id=0,
            access_token="old_access",
            refresh_token="mocked_refresh",
            expires_at=int((datetime.utcnow() - timedelta(hours=1)).timestamp())  # expired to trigger refresh
        ))
        db_session.commit()

    # Step 2: Refresh (using Authorization header)
    headers = {"Authorization": f"Bearer {refresh_token}"}
    resp = client.post("/auth/refresh/0", headers=headers)
    assert resp.status_code == 200

    # Step 3: Logout
    resp = client.post("/auth/logout/0", headers=headers)
    assert resp.status_code == 200


def test_invalid_login_rejected(client):
    """Test that invalid credentials are rejected."""
    resp = client.post("/auth/login", json={"username": "wrong", "password": "bad"})
    assert resp.status_code == 401


def test_invalid_refresh_token(client):
    """Test that an invalid refresh token is rejected."""
    headers = {"Authorization": "Bearer not.a.real.token"}
    resp = client.post("/auth/refresh/0", headers=headers)
    assert resp.status_code == 401


def test_expired_refresh_token(client):
    """Test refresh fails with an expired token."""
    secret = os.environ.get("SECRET_KEY", "testsecret")

    expired_token = jwt.encode(
        {
            "sub": "admin",
            "exp": datetime.utcnow() - timedelta(seconds=1)
        },
        secret,
        algorithm="HS256"
    )

    resp = client.post("/auth/refresh/0", headers={"Authorization": f"Bearer {expired_token}"})
    print(f"⏰ Expired refresh status: {resp.status_code}, Body: {resp.data.decode()}")
    assert resp.status_code == 401
