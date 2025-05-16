# src/routes/sync_routes.py

import os
import traceback
import requests
from flask import Blueprint, request, jsonify
from src.services.activity_sync import sync_recent_activities
from src.db import get_tokens_pg, save_tokens_pg

SYNC = Blueprint("sync", __name__)
CRON_KEY = os.getenv("CRON_SECRET_KEY")
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")


def get_valid_access_token(athlete_id):
    tokens = get_tokens_pg(athlete_id)
    if not tokens:
        raise Exception(f"No tokens for athlete {athlete_id}")
    access, refresh = tokens["access_token"], tokens["refresh_token"]

    # Test current token
    r = requests.get(
        "https://www.strava.com/api/v3/athlete",
        headers={"Authorization": f"Bearer {access}"},
    )
    if r.status_code == 401:
        # Refresh token flow
        rr = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
        )
        rr.raise_for_status()
        data = rr.json()
        access = data["access_token"]
        # Persist refreshed tokens using the correct DB helper
        save_tokens_pg(athlete_id, access, data["refresh_token"])

    return access


@SYNC.route("/sync-strava-to-db/<int:athlete_id>")
def sync_to_db(athlete_id):
    key = request.args.get("key")
    if CRON_KEY and key != CRON_KEY:
        return jsonify(error="Unauthorized"), 401

    try:
        token = get_valid_access_token(athlete_id)
        inserted = sync_recent_activities(athlete_id, token)
        return jsonify(synced=inserted), 200

    except Exception as e:
        # Log full traceback for debugging
        traceback.print_exc()
        # Return a clean JSON error
        return jsonify(error="Sync failed", details=str(e)), 500
