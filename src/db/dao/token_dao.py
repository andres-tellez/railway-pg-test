# src/db/dao/token_dao.py

from datetime import datetime
from sqlalchemy.exc import NoResultFound, IntegrityError
from flask import current_app
import os

from src.db.db_session import get_session  # ✅ Fixed import: consistent db_session usage
from src.db.models.tokens import Token


def get_tokens_sa(session, athlete_id):
    """
    Retrieve access, refresh, and expiration tokens for the given athlete using SQLAlchemy.
    """
    try:
        token = session.query(Token).filter_by(athlete_id=athlete_id).one()
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at   # ✅ ADDED THIS FIELD
        }
    except NoResultFound:
        return None


def save_tokens_sa(session, athlete_id, access_token, refresh_token, expires_at=None):
    """
    Save or update tokens for an athlete using SQLAlchemy.

    For Strava, tokens are opaque (not JWT), so we skip decoding and simply store them.
    """
    try:
        # If expires_at not provided, fallback to reasonable default (1 hour)
        if not expires_at:
            now_ts = int(datetime.utcnow().timestamp())
            expires_at = now_ts + 3600

        token = session.query(Token).filter_by(athlete_id=athlete_id).one_or_none()

        if token:
            token.access_token = access_token
            token.refresh_token = refresh_token
            token.expires_at = expires_at
        else:
            token = Token(
                athlete_id=athlete_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at
            )
            session.add(token)

        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise RuntimeError(f"Failed to save tokens via SQLAlchemy: {e}")
    except Exception as e:
        session.rollback()
        raise RuntimeError(f"Token saving failed: {e}")


def get_valid_access_token_sa(session, athlete_id):
    """
    Retrieve a valid (non-expired) access token using SQLAlchemy.
    """
    try:
        token = session.query(Token).filter_by(athlete_id=athlete_id).one_or_none()
        if not token:
            return None

        now_ts = int(datetime.utcnow().timestamp())
        if token.expires_at > now_ts:
            return token.access_token
        else:
            print(f"⚠️ Token expired for athlete {athlete_id}")
            return None
    except Exception as e:
        raise RuntimeError(f"Failed to fetch valid access token: {e}")
