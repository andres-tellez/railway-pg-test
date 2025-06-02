# src/routes/sync_routes.py

import os
import traceback
import requests
from flask import Blueprint, request, jsonify

# Service for syncing activities
from src.services.activity_sync import sync_recent_activities
from src.services.strava import generate_strava_auth_url

# DAO imports (SQLAlchemy-only)
from src.db.db_session import get_session
from src.db.dao.token_dao import get_valid_access_token_sa

SYNC = Blueprint("sync", __name__)

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
        session = get_session()

        # Use SQLAlchemy DAO helper
        access_token = get_valid_access_token_sa(session, athlete_id)

        if not access_token:
            auth_url = generate_strava_auth_url(athlete_id)
            return jsonify(
                error="No tokens found for athlete",
                auth_url=auth_url
            ), 401

        inserted = sync_recent_activities(
            session=session,
            athlete_id=athlete_id,
            access_token=access_token
        )

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
