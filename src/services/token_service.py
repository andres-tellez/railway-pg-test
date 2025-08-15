# src/services/token_service.py
import logging
import requests
from datetime import datetime
import jwt

import src.utils.config as config
from src.db.db_session import get_session as db_get_session
from src.db.dao.token_dao import get_tokens_sa, insert_token_sa
from src.db.models.tokens import Token

# ✅ Use a simple "ensure athlete exists" flow.
# Prefer DAO helpers if available; otherwise fall back to a tiny local insert.
try:
    from src.db.dao.athlete_dao import (
        get_athlete_id_from_strava_id,
        insert_athlete,  # expected helper for minimal insert
    )
except Exception:  # fallback if insert_athlete doesn't exist in your DAO yet
    from src.db.dao.athlete_dao import get_athlete_id_from_strava_id  # type: ignore
    from src.db.models.athletes import Athlete

    def insert_athlete(session, strava_athlete_id: int) -> int:  # type: ignore
        a = Athlete(strava_athlete_id=strava_athlete_id)
        session.add(a)
        session.commit()
        session.refresh(a)
        return a.id


logger = logging.getLogger(__name__)


def get_session():
    return db_get_session()


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
        expires_at=tokens["expires_at"],
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


def store_tokens_from_callback(code, session, redirect_uri):
    redirect_uri_clean = redirect_uri.strip().rstrip(";")
    print(
        f"[TokenService] Using cleaned redirect_uri: '{redirect_uri_clean}'", flush=True
    )

    payload = {
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri_clean,
    }
    print(f"[TokenService] Sending POST data to Strava token endpoint:\n{payload}")

    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data=payload,
    )
    response.raise_for_status()
    token_data = response.json()

    # --- Changed: validate and ensure athlete row exists (no name/email required) ---
    athlete = token_data.get("athlete")
    if not athlete or "id" not in athlete:
        raise KeyError("❌ Strava callback response missing athlete ID")

    strava_athlete_id = athlete["id"]

    # Ensure an internal athletes row exists mapped to this Strava ID.
    internal_id = get_athlete_id_from_strava_id(session, strava_athlete_id)
    if internal_id is None:
        internal_id = insert_athlete(session, strava_athlete_id)
        print(
            f"🆕 Inserted athlete row id={internal_id} for Strava #{strava_athlete_id}",
            flush=True,
        )
    else:
        print(
            f"ℹ️ Found athlete row id={internal_id} for Strava #{strava_athlete_id}",
            flush=True,
        )
    # -------------------------------------------------------------------------------

    # We key tokens by Strava athlete id (existing behavior).
    insert_token_sa(
        session=session,
        athlete_id=strava_athlete_id,
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_at=token_data["expires_at"],
    )

    print(f"✅ Token stored for athlete: {strava_athlete_id}", flush=True)
    return strava_athlete_id


def exchange_code_for_token(code, redirect_uri=None):
    if redirect_uri is None:
        redirect_uri = config.STRAVA_REDIRECT_URI.strip().rstrip(";")
    else:
        redirect_uri = redirect_uri.strip().rstrip(";")

    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    response.raise_for_status()
    return response.json()


def get_authorization_url():
    redirect_uri = config.STRAVA_REDIRECT_URI.strip().rstrip(";")
    client_id = config.STRAVA_CLIENT_ID
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    return url
