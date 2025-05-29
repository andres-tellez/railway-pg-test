import os
import traceback
import requests
from flask import Blueprint, request, jsonify
from src.services.activity_sync import sync_recent_activities

from src.core import get_engine, get_session
from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa
from src.db.init_db import get_tokens_pg, save_tokens_pg

SYNC = Blueprint("sync", __name__)

def get_valid_access_token(athlete_id):
    """
    Retrieve a valid Strava access token, refreshing it if necessary.
    Supports SQLAlchemy and psycopg2 backends.
    """
    db_url = os.getenv("DATABASE_URL")
    use_sqlalchemy = db_url and not db_url.startswith("sqlite")

    if use_sqlalchemy:
        session = get_session(get_engine(db_url))
        tokens = get_tokens_sa(session, athlete_id)
    else:
        tokens = get_tokens_pg(athlete_id)

    if not tokens:
        raise Exception(f"No tokens found for athlete {athlete_id}")

    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # Validate the access token
    r = requests.get(
        "https://www.strava.com/api/v3/athlete",
        headers={"Authorization": f"Bearer {access}"},
    )

    if r.status_code == 401:
        # Refresh the token
        rr = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": os.getenv("STRAVA_CLIENT_ID"),
                "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
        )
        if rr.status_code != 200:
            print("❌ Strava token refresh failed:", rr.text, flush=True)
            raise RuntimeError(f"Strava token refresh failed: {rr.text}")

        data = rr.json()
        access = data["access_token"]
        new_refresh = data["refresh_token"]

        # Save refreshed tokens
        if use_sqlalchemy:
            save_tokens_sa(session, athlete_id, access, new_refresh)
        else:
            save_tokens_pg(athlete_id, access, new_refresh)

    return access

@SYNC.route("/sync-strava-to-db/<int:athlete_id>")
def sync_to_db(athlete_id):
    """Endpoint for CRON-based syncs using a secret key."""
    cron_key = os.getenv("CRON_SECRET_KEY")
    key = request.args.get("key")
    print(f"🔐 Incoming key: {key}")
    print(f"🔐 Expected key from env: {cron_key}")

    if cron_key and key != cron_key:
        return jsonify(error="Unauthorized"), 401

    try:
        token = get_valid_access_token(athlete_id)
        inserted = sync_recent_activities(athlete_id, token)
        return jsonify(synced=inserted), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify(error="Sync failed", details=str(e)), 500

@SYNC.route("/init-db")
def init_db_route():
    """Manual DB initializer (same as /run.py -- init-db)."""
    from src.services.db_bootstrap import init_db
    try:
        init_db()
        return "✅ init_db() completed successfully", 200
    except Exception as e:
        traceback.print_exc()
        return f"❌ Error initializing DB: {e}", 500
