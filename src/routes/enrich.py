# src/routes/enrich.py

from flask import Blueprint, jsonify, request
from src.services import enrichment_sync
from src.db.db_session import get_session
from sqlalchemy import text

enrich_bp = Blueprint("enrich", __name__)

@enrich_bp.route("/status", methods=["GET"])
def status():
    """Quick health check"""
    return jsonify({"enrich": "ok"}), 200

@enrich_bp.route("/activity/<int:activity_id>", methods=["POST"])
def enrich_single(activity_id):
    """Trigger enrichment for a single activity directly"""
    session = get_session()
    try:
        # Grab athlete_id directly from DB for safety
        row = session.execute(
            text("SELECT athlete_id FROM activities WHERE activity_id = :id"),
            {"id": activity_id}
        ).fetchone()

        if not row:
            return jsonify({"error": f"Activity {activity_id} not found"}), 404

        athlete_id = row.athlete_id

        # ✅ Use your service helper that automatically handles token refresh
        enrichment_sync.enrich_one_activity_with_refresh(
            session=session,
            athlete_id=athlete_id,
            activity_id=activity_id
        )

        return jsonify({"status": f"Activity {activity_id} enriched"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        session.close()

@enrich_bp.route("/batch-enrich", methods=["POST"])
def enrich_batch():
    """
    Enrich multiple activities for an athlete.
    You can pass ?athlete_id=X&batch=N
    """
    athlete_id = request.args.get("athlete_id", type=int)
    batch = request.args.get("batch", default=20, type=int)

    if not athlete_id:
        return jsonify({"error": "Missing athlete_id"}), 400

    try:
        enrichment_sync.enrichment_loop(athlete_id, batch_size=batch)
        return jsonify({"status": f"Batch enrichment complete for athlete {athlete_id}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
