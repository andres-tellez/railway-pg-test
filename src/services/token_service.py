import os
import requests
import urllib.parse
import jwt
from datetime import datetime, timedelta

from flask import current_app, has_app_context

from src.db.dao.token_dao import get_tokens_sa, insert_token_sa, delete_tokens_sa
from src.db.db_session import get_engine, get_session

# ---------- Utility Constants ----------
ACCESS_TOKEN_EXP = lambda: int(os.getenv("ACCESS_TOKEN_EXP", 900))        # 15 minutes
REFRESH_TOKEN_EXP = lambda: int(os.getenv("REFRESH_TOKEN_EXP", 604800))   # 7 days


# ---------- Token Management ----------
def get_valid_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    if is_expired(token_data["expires_at"]):
        token_data = refresh_access_token(session, athlete_id)

    return token_data["access_token"]

def is_expired(expires_at):
    now_epoch = int(datetime.utcnow().timestamp())
    return expires_at <= now_epoch

def refresh_access_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    refresh_token = token_data["refresh_token"]

    tokens = refresh_token_static(refresh_token)

    insert_token_sa(
        session=session,
        athlete_id=athlete_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"]
    )

    return tokens

def refresh_token_static(refresh_token):
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")

    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    response.raise_for_status()
    return response.json()

def exchange_code_for_token(code):
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    redirect_uri = os.getenv("REDIRECT_URI")

    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": int(client_id),
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
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
    client_id = os.getenv("STRAVA_CLIENT_ID")
    redirect_uri = os.getenv("STRAVA_REDIRECT_URI")

    if not client_id or not redirect_uri:
        raise ValueError("Missing STRAVA_CLIENT_ID or STRAVA_REDIRECT_URI in environment")

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "auto",
        "scope": "read,activity:read_all"
    }

    return f"https://www.strava.com/oauth/authorize?{urllib.parse.urlencode(params)}"

def store_tokens_from_callback(code, session):
    token_response = exchange_code_for_token(code)

    athlete_id = token_response["athlete"]["id"]
    access_token = token_response["access_token"]
    refresh_token = token_response["refresh_token"]
    expires_at = token_response["expires_at"]

    insert_token_sa(session, athlete_id, access_token, refresh_token, expires_at)
    return athlete_id


# ---------- Admin Login / JWT ----------
def resolve_db_url():
    if has_app_context():
        return current_app.config.get("DATABASE_URL", os.getenv("DATABASE_URL"))
    return os.getenv("DATABASE_URL")

def login_user(data: dict) -> tuple[str, str]:
    username = data.get("username")
    password = data.get("password")

    if username != os.getenv("ADMIN_USER") or password != os.getenv("ADMIN_PASS"):
        raise PermissionError("Invalid credentials")

    now = datetime.utcnow()
    secret = os.getenv("SECRET_KEY", "dev")

    access_payload = {
        "sub": username,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_EXP()),
    }
    refresh_payload = {
        "sub": username,
        "exp": now + timedelta(seconds=REFRESH_TOKEN_EXP()),
    }

    access_token = jwt.encode(access_payload, secret, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, secret, algorithm="HS256")

    expires_at = int(now.timestamp()) + REFRESH_TOKEN_EXP()

    session = get_session()
    insert_token_sa(session, athlete_id=0, access_token=access_token, refresh_token=refresh_token, expires_at=expires_at)

    return access_token, refresh_token

def refresh_token(refresh_token_str: str) -> str:
    secret = os.getenv("SECRET_KEY", "dev")
    try:
        payload = jwt.decode(refresh_token_str, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise PermissionError("Refresh token expired")
    except jwt.InvalidTokenError:
        raise PermissionError("Invalid refresh token")

    username = payload.get("sub")
    session = get_session()
    tokens = get_tokens_sa(session, athlete_id=0)

    if not tokens or tokens.get("refresh_token") != refresh_token_str:
        raise PermissionError("Refresh token not recognized")

    now = datetime.utcnow()
    new_payload = {
        "sub": username,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_EXP()),
    }

    return jwt.encode(new_payload, secret, algorithm="HS256")

def logout_user(refresh_token_str: str) -> None:
    # No-op
    pass


def delete_athlete_tokens(session, athlete_id):
    """Deletes token record for the given athlete"""
    delete_tokens_sa(session, athlete_id)
    return True
