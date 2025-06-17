import logging
import requests
import urllib.parse
import jwt
from datetime import datetime, timedelta

from flask import current_app, has_app_context

import src.utils.config as config
from src.db.dao.token_dao import get_tokens_sa, insert_token_sa, delete_tokens_sa
from src.db.db_session import get_engine, get_session

from src.db.dao.athlete_dao import insert_athlete  


logger = logging.getLogger(__name__)


# ---------- Helpers ----------
def is_expired(expires_at):
    return expires_at <= int(datetime.utcnow().timestamp())

def resolve_db_url():
    return config.DATABASE_URL


# ---------- Token Management ----------
def get_valid_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    if is_expired(token_data["expires_at"]):
        token_data = refresh_access_token(session, athlete_id)

    return token_data["access_token"]

def refresh_access_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No refresh token available for athlete {athlete_id}")

    tokens = refresh_token_static(token_data["refresh_token"])

    insert_token_sa(
        session=session,
        athlete_id=athlete_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"]
    )

    return tokens

def refresh_token_static(refresh_token):
    logger.info("Refreshing Strava token...")
    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    logger.debug(f"Strava response: {response.status_code} - {response.text}")
    response.raise_for_status()
    return response.json()

def exchange_code_for_token(code):
    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config.STRAVA_REDIRECT_URI
        },
    )
    response.raise_for_status()
    return response.json()

def refresh_token_if_expired(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise ValueError(f"No tokens found for athlete {athlete_id}")

    if is_expired(token_data["expires_at"]):
        refresh_access_token(session, athlete_id)
        return True
    return False


# ---------- Strava OAuth Routing ----------
def get_authorization_url():
    if not config.STRAVA_CLIENT_ID or not config.STRAVA_REDIRECT_URI:
        raise ValueError("Missing STRAVA_CLIENT_ID or STRAVA_REDIRECT_URI in environment")

    params = {
        "client_id": config.STRAVA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": config.STRAVA_REDIRECT_URI,
        "approval_prompt": "auto",
        "scope": "read,activity:read_all"
    }

    return f"https://www.strava.com/oauth/authorize?{urllib.parse.urlencode(params)}"

def store_tokens_from_callback(code, session):
    token_response = exchange_code_for_token(code)

    athlete_info = token_response.get("athlete", {})
    athlete_id = athlete_info.get("id")
    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_at = token_response.get("expires_at")

    insert_token_sa(session, athlete_id, access_token, refresh_token, expires_at)

    # 👇 NEW: insert athlete into the athletes table
    if athlete_info:
        insert_athlete(
            session,
            strava_athlete_id=athlete_id,
            name=f"{athlete_info.get('firstname', '')} {athlete_info.get('lastname', '')}".strip(),
            email=athlete_info.get("email")
        )

    return athlete_id


# ---------- Admin Login / JWT ----------
def login_user(data: dict) -> tuple[str, str]:
    username = data.get("username")
    password = data.get("password")

    if username != config.ADMIN_USER or password != config.ADMIN_PASS:
        raise PermissionError("Invalid credentials")

    now = datetime.utcnow()

    access_payload = {
        "sub": username,
        "exp": now + timedelta(seconds=config.ACCESS_TOKEN_EXP),
    }
    refresh_payload = {
        "sub": username,
        "exp": now + timedelta(seconds=config.REFRESH_TOKEN_EXP),
    }

    access_token = jwt.encode(access_payload, config.SECRET_KEY, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, config.SECRET_KEY, algorithm="HS256")

    expires_at = int(now.timestamp()) + config.REFRESH_TOKEN_EXP

    session = get_session()
    insert_token_sa(session, athlete_id=config.ADMIN_ATHLETE_ID, access_token=access_token, refresh_token=refresh_token, expires_at=expires_at)

    return access_token, refresh_token

def refresh_token(refresh_token_str: str) -> str:
    try:
        payload = jwt.decode(refresh_token_str, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise PermissionError("Refresh token expired")
    except jwt.InvalidTokenError:
        raise PermissionError("Invalid refresh token")

    username = payload.get("sub")
    session = get_session()
    tokens = get_tokens_sa(session, athlete_id=config.ADMIN_ATHLETE_ID)

    if not tokens or tokens.get("refresh_token") != refresh_token_str:
        raise PermissionError("Refresh token not recognized")

    now = datetime.utcnow()
    new_payload = {
        "sub": username,
        "exp": now + timedelta(seconds=config.ACCESS_TOKEN_EXP),
    }

    return jwt.encode(new_payload, config.SECRET_KEY, algorithm="HS256")

def logout_user(refresh_token_str: str) -> None:
    pass

def delete_athlete_tokens(session, athlete_id):
    delete_tokens_sa(session, athlete_id)
    return True
