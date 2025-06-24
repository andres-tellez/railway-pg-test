import logging
import requests
from datetime import datetime

import src.utils.config as config
from src.db.dao.token_dao import get_tokens_sa, insert_token_sa
from src.db.models.tokens import Token

logger = logging.getLogger(__name__)


def is_expired(expires_at):
    return expires_at <= int(datetime.utcnow().timestamp())


def get_valid_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    if is_expired(token_data["expires_at"]):
        return refresh_access_token(session, athlete_id)["access_token"]

    return token_data["access_token"]


def refresh_access_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No refresh token available for athlete {athlete_id}")

    tokens = refresh_token_static(token_data["refresh_token"])
    print("🔁 Refreshed token:", tokens, flush=True)
    insert_token_sa(
        session=session,
        athlete_id=athlete_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"]
    )
    return tokens


def refresh_token_static(refresh_token):
    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    response.raise_for_status()
    return response.json()


def refresh_token_if_expired(session, athlete_id):
    token = session.query(Token).filter_by(athlete_id=athlete_id).first()
    if not token:
        raise ValueError(f"No token found for athlete ID {athlete_id}")

    now = datetime.utcnow().timestamp()
    if token.expires_at <= now:
        refreshed = refresh_token_static(token.refresh_token)
        token.access_token = refreshed["access_token"]
        token.refresh_token = refreshed["refresh_token"]
        token.expires_at = refreshed["expires_at"]
        session.commit()
        return True
    return False


def delete_athlete_tokens(session, athlete_id):
    deleted = session.query(Token).filter_by(athlete_id=athlete_id).delete()
    session.commit()
    return deleted


# ✅ MISSING FUNCTION: Store tokens after OAuth callback
def store_tokens_from_callback(code, session):
    print(f"🔁 Exchanging code for tokens: {code}", flush=True)
    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code"
        },
    )
    response.raise_for_status()
    token_data = response.json()

    athlete = token_data.get("athlete")
    if not athlete or "id" not in athlete:
        raise KeyError("❌ Strava callback response missing athlete ID")

    athlete_id = athlete["id"]
    insert_token_sa(
        session=session,
        athlete_id=athlete_id,
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_at=token_data["expires_at"]
    )

    print(f"✅ Token stored for athlete: {athlete_id}", flush=True)
    return athlete_id
