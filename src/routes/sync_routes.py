# routes/sync_routes.py

from flask import Blueprint, request, jsonify
from src.services.activity_sync import sync_recent_activities
from db import get_tokens_pg
import os
import requests

SYNC = Blueprint("sync", __name__)
CRON_KEY = os.getenv("CRON_SECRET_KEY")
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")


def get_valid_access_token(athlete_id):
    tokens = get_tokens_pg(athlete_id)
    if not tokens:
        raise Exception(f"No tokens for athlete {athlete_id}")
    access, refresh = tokens["access_token"], tokens["refresh_token"]

    r = requests.get(
        "https://www.strava.com/api/v3/athlete",
        headers={"Authorization": f"Bearer {access}"},
    )
    if r.status_code == 401:
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
        from db import save_token_pg

        save_token_pg(athlete_id, access, data["refresh_token"])

    return access


@SYNC.route("/sync-strava-to-db/<int:athlete_id>")
def sync_to_db(athlete_id):
    key = request.args.get("key")
    if CRON_KEY and key != CRON_KEY:
        return jsonify(error="Unauthorized"), 401

    token = get_valid_access_token(athlete_id)
    inserted = sync_recent_activities(athlete_id, token)
    return jsonify(synced=inserted)
