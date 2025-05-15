"""
Module: src/services/auth.py
Authentication service for Smart Marathon Coach.

Provides:
- login_user(): validate credentials and issue tokens.
- refresh_token(): exchange a refresh token for a new access token.
- logout_user(): revoke a refresh token.
"""

import os
import jwt
import datetime
from src.db import save_tokens_pg, get_tokens_pg

# Token expiration durations (in seconds)
ACCESS_TOKEN_EXP = int(os.getenv("ACCESS_TOKEN_EXP", 900))       # 15 minutes
REFRESH_TOKEN_EXP = int(os.getenv("REFRESH_TOKEN_EXP", 604800))  # 7 days
JWT_SECRET = os.getenv("SECRET_KEY", "dev")  # fallback secret

def login_user(data: dict) -> tuple[str, str]:
    """
    Authenticate user and issue access + refresh tokens.

    Args:
        data (dict): must contain 'username' and 'password'

    Returns:
        (access_token, refresh_token)
    """
    username = data.get("username")
    password = data.get("password")

    # Validate against admin credentials from .env
    if username != os.getenv("ADMIN_USER") or password != os.getenv("ADMIN_PASS"):
        raise PermissionError("Invalid credentials")

    now = datetime.datetime.utcnow()
    access_payload = {
        "sub": username,
        "exp": now + datetime.timedelta(seconds=ACCESS_TOKEN_EXP),
    }
    refresh_payload = {
        "sub": username,
        "exp": now + datetime.timedelta(seconds=REFRESH_TOKEN_EXP),
    }

    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm="HS256")

    # Save tokens to DB (hardcoding athlete_id=0 for now)
    save_tokens_pg(athlete_id=0, access_token=access_token, refresh_token=refresh_token)

    return access_token, refresh_token

def refresh_token(refresh_token_str: str) -> str:
    """
    Exchange refresh token for a new access token.

    Args:
        refresh_token_str (str): a JWT refresh token

    Returns:
        access_token (str)
    """
    try:
        payload = jwt.decode(refresh_token_str, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise PermissionError("Refresh token expired")
    except jwt.InvalidTokenError:
        raise PermissionError("Invalid refresh token")

    username = payload.get("sub")

    # Optionally verify token in DB
    tokens = get_tokens_pg(athlete_id=0)
    if not tokens or tokens.get("refresh_token") != refresh_token_str:
        raise PermissionError("Refresh token not recognized")

    now = datetime.datetime.utcnow()
    new_payload = {
        "sub": username,
        "exp": now + datetime.timedelta(seconds=ACCESS_TOKEN_EXP),
    }

    return jwt.encode(new_payload, JWT_SECRET, algorithm="HS256")

def logout_user(refresh_token_str: str) -> None:
    """
    Revoke refresh token.

    Args:
        refresh_token_str (str): token to revoke

    Note:
        Not implemented — you'd update DB to invalidate or delete the token.
    """
    pass  # For now, no-op
