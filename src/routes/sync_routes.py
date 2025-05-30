import os
import traceback
import requests
from flask import Blueprint, request, jsonify
from src.services.activity_sync import sync_recent_activities
from src.services.strava import generate_strava_auth_url

# DAO imports
from src.core import get_engine, get_session

# ✅ SQLAlchemy-based Token DAO
from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa

# ✅ Activity DAO (pure SQLAlchemy)
from src.db.dao.activity_dao import upsert_activities  # Updated to use upsert_activities

# ✅ low-level connection helper
from src.db.init_db import get_conn

SYNC = Blueprint("sync", __name__)

def get_valid_access_token(athlete_id):
    """
    Retrieve a valid Strava access token, refreshing if needed.
    Returns None if no token exists yet.
    """
    db_url = os.getenv("DATABASE_URL")
    use_sqlalchemy = db_url and not db_url.startswith("sqlite")

    session = None
    tokens = None

    if use_sqlalchemy:
        engine = get_engine(db_url)
        session = get_session(engine)
        tokens = get_tokens_sa(session, athlete_id)
    else:
        tokens = get_tokens_pg(athlete_id)

    if not tokens:
        if use_sqlalchemy:
            session.close()
        return None

    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # ✅ Validate token with Strava API
    try:
        r = requests.get(
            "https://www.strava.com/api/v3/athlete",
            headers={"Authorization": f"Bearer {access}"},
            timeout=5,
        )
        if r.status_code == 200:
            if use_sqlalchemy:
                session.close()
            return access  # token still valid
    except requests.RequestException as net_err:
        print(f"⚠️ Network error during token check: {net_err}", flush=True)

    # ✅ Refresh token if expired or invalid
    try:
        rr = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": os.getenv("STRAVA_CLIENT_ID"),
                "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
            timeout=5,
        )

        if rr.status_code != 200:
            raise RuntimeError(f"Strava token refresh failed: {rr.text}")

        data = rr.json()
        access = data["access_token"]
        new_refresh = data["refresh_token"]

        if use_sqlalchemy:
            save_tokens_sa(session, athlete_id, access, new_refresh)
            session.close()
        else:
            save_tokens_pg(athlete_id, access, new_refresh)

        return access

    except requests.RequestException as e:
        raise RuntimeError(f"Request error during token refresh: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error during token refresh: {e}")

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
        access_token = get_valid_access_token(athlete_id)
        if not access_token:
            auth_url = generate_strava_auth_url(athlete_id)
            return jsonify(
                error="No tokens found for athlete",
                auth_url=auth_url
            ), 401

        # ✅ Handle correct DB connection
        db_url = os.getenv("DATABASE_URL")
        if db_url and not db_url.startswith("sqlite"):
            engine = get_engine(db_url)
            conn = engine.connect()
        else:
            conn = get_conn(db_url)

        # Use the upsert_activities method to insert/update activities
        activities = []  # This should be populated with the activities data
        inserted = upsert_activities(conn, athlete_id, activities)  # Using upsert_activities here

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
