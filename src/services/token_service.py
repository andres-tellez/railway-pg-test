# src/services/token_service.py

import os
import requests
from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa
from datetime import datetime

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

    save_tokens_sa(
        session,
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
