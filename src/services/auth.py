# src/services/auth.py

import os
import jwt
import datetime
from flask import current_app, has_app_context

from src.db_core import get_engine, get_session
from src.dao.token_dao import get_tokens_sa, save_tokens_sa

ACCESS_TOKEN_EXP = lambda: int(os.getenv("ACCESS_TOKEN_EXP", 900))        # 15 minutes
REFRESH_TOKEN_EXP = lambda: int(os.getenv("REFRESH_TOKEN_EXP", 604800))   # 7 days

def resolve_db_url():
    if has_app_context():
        return current_app.config.get("DATABASE_URL", os.getenv("DATABASE_URL"))
    return os.getenv("DATABASE_URL")

def login_user(data: dict) -> tuple[str, str]:
    username = data.get("username")
    password = data.get("password")

    if username != os.getenv("ADMIN_USER") or password != os.getenv("ADMIN_PASS"):
        raise PermissionError("Invalid credentials")

    now = datetime.datetime.utcnow()
    secret = os.getenv("SECRET_KEY", "dev")

    access_payload = {
        "sub": username,
        "exp": now + datetime.timedelta(seconds=ACCESS_TOKEN_EXP()),
    }
    refresh_payload = {
        "sub": username,
        "exp": now + datetime.timedelta(seconds=REFRESH_TOKEN_EXP()),
    }

    access_token = jwt.encode(access_payload, secret, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, secret, algorithm="HS256")

    db_url = resolve_db_url()
    session = get_session(get_engine(db_url))
    save_tokens_sa(session, athlete_id=0, access_token=access_token, refresh_token=refresh_token)

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
    db_url = resolve_db_url()
    session = get_session(get_engine(db_url))
    tokens = get_tokens_sa(session, athlete_id=0)

    if not tokens or tokens.get("refresh_token") != refresh_token_str:
        raise PermissionError("Refresh token not recognized")

    now = datetime.datetime.utcnow()
    new_payload = {
        "sub": username,
        "exp": now + datetime.timedelta(seconds=ACCESS_TOKEN_EXP()),
    }

    return jwt.encode(new_payload, secret, algorithm="HS256")

def logout_user(refresh_token_str: str) -> None:
    # No-op
    pass
