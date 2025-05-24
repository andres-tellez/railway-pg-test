# src/db/dao/token_dao.py

from sqlalchemy.exc import NoResultFound, IntegrityError
from flask import current_app
from src.db.models.tokens import Token
from src.utils.jwt_utils import decode_token  # Required to extract 'exp' from JWT


def get_tokens_sa(session, athlete_id):
    try:
        token = session.query(Token).filter_by(athlete_id=athlete_id).one()
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token
        }
    except NoResultFound:
        return None


def save_tokens_sa(session, athlete_id, access_token, refresh_token):
    try:
        # Decode access token to extract expiry
        secret = current_app.config["SECRET_KEY"]
        token_data = decode_token(access_token, secret)
        expires_at = token_data.get("exp")
        if not expires_at:
            raise ValueError("Access token missing 'exp' field")

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
        raise RuntimeError(f"Token decoding or saving failed: {e}")
