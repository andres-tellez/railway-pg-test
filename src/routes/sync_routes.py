# src/routes/sync_routes.py

import os
import traceback
import requests
from flask import Blueprint, request, jsonify
from src.services.activity_sync import sync_recent_activities

SYNC = Blueprint("sync", __name__)


def get_valid_access_token(athlete_id):
    from src.db import get_tokens_pg
    from src.db_core import get_engine, get_session
    from src.dao.token_dao import get_tokens_sa, save_tokens_sa

    db_url = os.getenv("DATABASE_URL")
    use_sqlalchemy = db_url and not db_url.startswith("sqlite")

    if use_sqlalchemy:
        session = get_session(get_engine(db_url))
        tokens = get_tokens_sa(session, athlete_id)
    else:
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
                "client_id": os.getenv("STRAVA_CLIENT_ID"),
                "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
        )
        rr.raise_for_status()
        data = rr.json()
        access = data["access_token"]

        if use_sqlalchemy:
            save_tokens_sa(session, athlete_id, access, data["refresh_token"])
        else:
            from src.db import save_tokens_pg
            save_tokens_pg(athlete_id, access, data["refresh_token"])

    return access


@SYNC.route("/sync-strava-to-db/<int:athlete_id>")
def sync_to_db(athlete_id):
    cron_key = os.getenv("CRON_SECRET_KEY")
    key = request.args.get("key")
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
    from src.services.db_bootstrap import init_db
    import traceback

    try:
        init_db()
        return "✅ init_db() completed successfully", 200
    except Exception as e:
        print("❌ Error in init_db:", e, flush=True)
        traceback.print_exc()
        return f"❌ Error initializing DB: {e}", 500
