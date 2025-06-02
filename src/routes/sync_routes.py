# src/routes/sync_routes.py

import os
import traceback
from flask import Blueprint, request, jsonify

# Services
from src.services.activity_sync import sync_recent, ensure_fresh_token
from src.services.strava import generate_strava_auth_url

# DAO imports (SQLAlchemy-only)
from src.db.db_session import get_session

SYNC = Blueprint("sync", __name__)

@SYNC.route("/sync-strava-to-db/<int:athlete_id>")
def sync_to_db(athlete_id):
    """Endpoint for CRON-based syncs using a secret key."""
    cron_key = os.getenv("CRON_SECRET_KEY")
    key = request.args.get("key")
    print(f"🔐 Incoming key: {key}")
    print(f"🔐 Expected key from env: {cron_key}")

    if not cron_key or key != cron_key:
        return jsonify(error="Unauthorized"), 401

    session = None
    try:
        session = get_session()

        # Fully handle token lookup + refresh
        try:
            access_token = ensure_fresh_token(session, athlete_id)
        except Exception as token_err:
            print("❌ Token retrieval or refresh failed:", token_err)
            auth_url = generate_strava_auth_url(athlete_id)
            return jsonify(
                error="Unable to obtain valid tokens.",
                auth_url=auth_url,
                details=str(token_err)
            ), 401

        inserted = sync_recent(
            session=session,
            athlete_id=athlete_id,
            access_token=access_token
        )

        return jsonify(synced=inserted), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify(error="Sync failed", details=str(e)), 500

    finally:
        if session:
            session.close()

@SYNC.route("/init-db")
def init_db_route():
    """Manual DB initializer (same as /run.py -- init-db)."""
    from src.db.init_db import init_db
    try:
        init_db()
        return "✅ init_db() completed successfully", 200
    except Exception as e:
        traceback.print_exc()
        return f"❌ Error initializing DB: {e}", 500
