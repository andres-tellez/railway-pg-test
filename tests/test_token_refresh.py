# tests/test_token_refresh.py

import pytest
from datetime import datetime, timedelta
from src.services.token_refresh import ensure_fresh_access_token
from src.db.models.tokens import Token
from src.db.dao.token_dao import save_tokens_sa

@pytest.fixture
def token_expired():
    return int((datetime.utcnow() - timedelta(hours=1)).timestamp())

@pytest.fixture
def token_valid():
    return int((datetime.utcnow() + timedelta(hours=1)).timestamp())

def test_token_refresh_logic(sqlalchemy_session, monkeypatch, token_valid, token_expired):
    athlete_id = 123456

    # Save valid token
    save_tokens_sa(sqlalchemy_session, athlete_id, "valid_access", "refresh_token", token_valid)

    # Should NOT call refresh if token is still valid
    monkeypatch.setattr(
        "src.services.token_refresh.refresh_strava_token",
        lambda rt: (_ for _ in ()).throw(Exception("Should not refresh"))
    )
    access_token = ensure_fresh_access_token(sqlalchemy_session, athlete_id)
    assert access_token == "valid_access"

    # Now simulate expired token
    save_tokens_sa(sqlalchemy_session, athlete_id, "old_access", "refresh_token", token_expired)

    # Mock refresh_strava_token correctly
    monkeypatch.setattr(
        "src.services.token_refresh.refresh_strava_token",
        lambda rt: {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_at": token_valid
        }
    )

    access_token = ensure_fresh_access_token(sqlalchemy_session, athlete_id)
    assert access_token == "new_access"

    # Verify DB state updated after refresh
    token_row = sqlalchemy_session.query(Token).filter_by(athlete_id=athlete_id).one()
    assert token_row.access_token == "new_access"
    assert token_row.refresh_token == "new_refresh"
    assert token_row.expires_at == token_valid
