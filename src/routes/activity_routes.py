from flask import Blueprint, jsonify, request
import os
import traceback
from sqlalchemy import text

from src.services.activity_service import ActivityIngestionService, run_enrichment_batch
from src.db.db_session import get_session
from src.db.models.activities import Activity

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
            {"id": activity_id}
        ).fetchone()

        if not row:
            return jsonify({"error": f"Activity {activity_id} not found"}), 404

        athlete_id = row.athlete_id

        service = ActivityIngestionService(session, athlete_id)
        service.enrich_single_activity(activity_id)  # ✅ Updated to match architectural guardrails

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

# -------- Sync Routes --------

@activity_bp.route("/sync/<int:athlete_id>")
def sync_strava_to_db(athlete_id):
    """Strava sync endpoint secured via CRON secret"""
    cron_key = os.getenv("CRON_SECRET_KEY")
    key = request.args.get("key")
    if not cron_key or key != cron_key:
        return jsonify(error="Unauthorized"), 401

    session = get_session()
    try:
        ingestion_service = ActivityIngestionService(session, athlete_id)
        inserted = ingestion_service.ingest_recent(lookback_days=30)
        return jsonify(inserted=inserted), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify(error="Sync failed", details=str(e)), 500
    finally:
        session.close()


