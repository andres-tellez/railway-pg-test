# src/db/dao/token_dao.py

from datetime import datetime
from sqlalchemy.exc import NoResultFound, IntegrityError
from flask import current_app
import os

from src.db.db_session import get_session  # ✅ consistent db_session usage
from src.db.models.tokens import Token
from sqlalchemy.dialects.postgresql import insert

def get_tokens_sa(session, athlete_id):
    """
    Retrieve access, refresh, and expiration tokens for the given athlete using SQLAlchemy.
    """
    try:
        token = session.query(Token).filter_by(athlete_id=athlete_id).one()
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at
        }
    except NoResultFound:
        return None



def insert_token_sa(session, athlete_id, access_token, refresh_token, expires_at):
    existing = session.query(Token).filter_by(athlete_id=athlete_id).first()

    if existing:
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.expires_at = expires_at
    else:
        new_token = Token(
            athlete_id=athlete_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at
        )
        session.add(new_token)

    session.commit()


def delete_tokens_sa(session, athlete_id):
    """
    Deletes token record for the given athlete ID.
    """
    session.query(Token).filter_by(athlete_id=athlete_id).delete()
    session.commit()