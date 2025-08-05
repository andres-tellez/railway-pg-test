"""
activity_routes.py

Enrichment-related endpoints only. All Strava activity ingestion must be run via CLI:

    ✅ USE THIS:
        python -m src.scripts.main_pipeline --athlete_id <id> --lookback_days <N>

    ⛔ DO NOT USE:
        /sync/<athlete_id> route — this is deprecated and will return 410 in prod.

Why:
- Ensures consistent ingestion logic
- Avoids API parameter drift
- Matches production cron jobs and test paths
"""

import os
import traceback
from flask import Blueprint, jsonify, request
from sqlalchemy import text

import src.utils.config as config
from src.services.activity_service import ActivityIngestionService, run_enrichment_batch
from src.db.db_session import get_session

activity_bp = Blueprint("activity", __name__)

# -------- Enrichment Routes --------


@activity_bp.route("/enrich/status", methods=["GET"])
def enrich_status():
    """Quick health check"""
    return jsonify({"enrich": "ok"}), 200


@activity_bp.route("/enrich/activity/<int:activity_id>", methods=["POST"])
def enrich_single(activity_id):
    """Trigger enrichment for a single activity"""
    session = get_session()
    try:
        row = session.execute(
            text("SELECT athlete_id FROM activities WHERE activity_id = :id"),
            {"id": activity_id},
        ).fetchone()

        if not row:
            return jsonify({"error": f"Activity {activity_id} not found"}), 404

        athlete_id = row.athlete_id
        service = ActivityIngestionService(session, athlete_id)
        service.enrich_single_activity(activity_id)

        return jsonify({"status": f"Activity {activity_id} enriched"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        session.close()


@activity_bp.route("/enrich/batch", methods=["POST"])
def enrich_batch():
    """Enrich a batch of activities for a given athlete"""
    athlete_id = request.args.get("athlete_id", type=int)
    batch = request.args.get("batch", default=20, type=int)

    if not athlete_id:
        return jsonify({"error": "Missing athlete_id"}), 400

    session = get_session()
    try:
        enriched = run_enrichment_batch(session, athlete_id, batch_size=batch)
        return jsonify({"status": "Batch enrichment complete", "count": enriched}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# -------- Deprecated Sync Route --------


@activity_bp.route("/sync/<int:athlete_id>")
def sync_strava_to_db(athlete_id):
    """
    ⚠️ DEPRECATED in production. Used only for test validation.
    """
    if os.getenv("FLASK_ENV") != "test":
        return (
            jsonify(
                {
                    "error": "This sync route is deprecated. Use CLI ingestion instead.",
                    "hint": "python -m src.scripts.main_pipeline --athlete_id <id> --lookback_days <N>",
                }
            ),
            410,
        )

    lookback = request.args.get("lookback", default=14, type=int)
    limit = request.args.get("limit", default=None, type=int)
    key = request.args.get("key")

    if key != config.CRON_SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    session = get_session()
    try:
        service = ActivityIngestionService(session, athlete_id)
        inserted = service.ingest_recent(lookback_days=lookback, max_activities=limit)
        return jsonify({"inserted": inserted}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
