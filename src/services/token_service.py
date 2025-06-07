# src/services/token_service.py

import os
import requests
from datetime import datetime
from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa

def get_valid_token(session, athlete_id):
    """
    Central token service entry point.
    Returns valid access token for athlete (refreshes if expired).
    """
    tokens = get_tokens_sa(session, athlete_id)
    if not tokens:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    now_ts = int(datetime.utcnow().timestamp())

    if tokens['expires_at'] > now_ts:
        return tokens['access_token']

    # Token expired — refresh
    refreshed = refresh_strava_token(tokens['refresh_token'])

    save_tokens_sa(
        session,
        athlete_id,
        refreshed['access_token'],
        refreshed['refresh_token'],
        refreshed['expires_at']
    )

    return refreshed['access_token']


def refresh_strava_token(refresh_token):
    """
    Calls Strava API to refresh an expired token.
    """
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")

    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": int(client_id),
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
