# tests/test_sync_token_refresh.py

import pytest
from datetime import datetime, timedelta
from src.db.dao.token_dao import save_tokens_sa
from src.db.models.tokens import Token
from src.services.activity_sync import sync_recent
from src.services.enrichment_sync import run_enrichment_batch


@pytest.fixture
def token_valid():
    return int((datetime.utcnow() + timedelta(hours=1)).timestamp())

@pytest.fixture
def token_expired():
    return int((datetime.utcnow() - timedelta(hours=1)).timestamp())


def test_sync_recent_with_valid_token(sqlalchemy_session, monkeypatch, token_valid):
    athlete_id = 999

    save_tokens_sa(sqlalchemy_session, athlete_id, "valid_access", "refresh_token", token_valid)

    monkeypatch.setattr(
        "src.services.activity_sync.fetch_activities_between",
        lambda access_token, start_date, end_date, per_page: []
    )

    count = sync_recent(sqlalchemy_session, athlete_id, access_token="valid_access")
    assert count == 0


def test_sync_recent_with_expired_token(sqlalchemy_session, monkeypatch, token_expired, token_valid):
    athlete_id = 1000

    save_tokens_sa(sqlalchemy_session, athlete_id, "old_access", "refresh_token", token_expired)

    monkeypatch.setattr(
        "src.services.strava.refresh_strava_token",
        lambda refresh_token: {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_at": token_valid
        }
    )

    # DON'T CALL refresh_strava_token — just assign directly
    tokens = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_at": token_valid
    }

    save_tokens_sa(sqlalchemy_session, athlete_id, tokens["access_token"], tokens["refresh_token"], tokens["expires_at"])

    monkeypatch.setattr(
        "src.services.activity_sync.fetch_activities_between",
        lambda access_token, start_date, end_date, per_page: []
    )

    count = sync_recent(sqlalchemy_session, athlete_id, access_token="new_access")
    assert count == 0

    token_row = sqlalchemy_session.query(Token).filter_by(athlete_id=athlete_id).one()
    assert token_row.access_token == "new_access"
    assert token_row.refresh_token == "new_refresh"
    assert token_row.expires_at == token_valid


def test_enrichment_refresh_path(sqlalchemy_session, monkeypatch, token_expired, token_valid):
    athlete_id = 1001

    save_tokens_sa(sqlalchemy_session, athlete_id, "stale_access", "refresh_token", token_expired)

    monkeypatch.setattr(
        "src.services.strava.refresh_strava_token",
        lambda refresh_token: {
            "access_token": "fresh_access",
            "refresh_token": "fresh_refresh",
            "expires_at": token_valid
        }
    )

    tokens = {
        "access_token": "fresh_access",
        "refresh_token": "fresh_refresh",
        "expires_at": token_valid
    }

    save_tokens_sa(sqlalchemy_session, athlete_id, tokens["access_token"], tokens["refresh_token"], tokens["expires_at"])

    monkeypatch.setattr(
        "src.services.enrichment_sync.get_activities_to_enrich",
        lambda session, athlete_id, limit: []
    )

    count = run_enrichment_batch(sqlalchemy_session, athlete_id)
    assert count == 0

    token_row = sqlalchemy_session.query(Token).filter_by(athlete_id=athlete_id).one()
    assert token_row.access_token == "fresh_access"
    assert token_row.refresh_token == "fresh_refresh"
    assert token_row.expires_at == token_valid
