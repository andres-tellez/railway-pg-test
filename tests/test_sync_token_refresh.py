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

    # Seed valid token
    save_tokens_sa(sqlalchemy_session, athlete_id, "valid_access", "refresh_token", token_valid)

    # Patch out fetch_activities_between to avoid real Strava call
    monkeypatch.setattr(
        "src.services.activity_sync.fetch_activities_between",
        lambda access_token, start_date, end_date, per_page: []
    )

    count = sync_recent(sqlalchemy_session, athlete_id, access_token="dummy-token")
    assert count == 0  # no activities returned


def test_sync_recent_with_expired_token(sqlalchemy_session, monkeypatch, token_expired, token_valid):
    athlete_id = 1000

    save_tokens_sa(sqlalchemy_session, athlete_id, "old_access", "refresh_token", token_expired)

    # ✅ Corrected patch path
    monkeypatch.setattr(
        "src.services.token_refresh.refresh_strava_token",
        lambda refresh_token: {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_at": token_valid
        }
    )

    # Patch out fetch_activities_between to avoid real Strava call
    monkeypatch.setattr(
        "src.services.activity_sync.fetch_activities_between",
        lambda access_token, start_date, end_date, per_page: []
    )

    count = sync_recent(sqlalchemy_session, athlete_id)
    assert count == 0

    # Verify DB updated
    token_row = sqlalchemy_session.query(Token).filter_by(athlete_id=athlete_id).one()
    assert token_row.access_token == "new_access"
    assert token_row.refresh_token == "new_refresh"
    assert token_row.expires_at == token_valid


def test_enrichment_refresh_path(sqlalchemy_session, monkeypatch, token_expired, token_valid):
    athlete_id = 1001

    save_tokens_sa(sqlalchemy_session, athlete_id, "stale_access", "refresh_token", token_expired)

    # ✅ Corrected patch path here too
    monkeypatch.setattr(
        "src.services.token_refresh.refresh_strava_token",
        lambda refresh_token: {
            "access_token": "fresh_access",
            "refresh_token": "fresh_refresh",
            "expires_at": token_valid
        }
    )

    # Patch enrichment DAO calls to avoid real DB work
    monkeypatch.setattr(
        "src.services.enrichment_sync.get_activities_to_enrich",
        lambda session, athlete_id, limit: []
    )

    count = run_enrichment_batch(sqlalchemy_session, athlete_id)
    assert count == 0

    # Verify refresh was persisted
    token_row = sqlalchemy_session.query(Token).filter_by(athlete_id=athlete_id).one()
    assert token_row.access_token == "fresh_access"
    assert token_row.refresh_token == "fresh_refresh"
    assert token_row.expires_at == token_valid
