from flask import Blueprint, jsonify, request
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from src.db.db_session import get_session
import logging

admin_bp = Blueprint("admin", __name__)
logger = logging.getLogger(__name__)


@admin_bp.route("/ping")
def ping():
    return "pong from admin"


@admin_bp.route("/trigger-ingest/<int:athlete_id>", methods=["POST"])
def trigger_ingestion(athlete_id):
    logger.info(f"⏱️ [Trigger] Received trigger-ingest for athlete_id={athlete_id}")
    session = get_session()

    try:
        lookback_days = request.args.get("lookback_days", default=None, type=int)
        max_activities = request.args.get("max_activities", default=10, type=int)

        result = run_full_ingestion_and_enrichment(
            session=session,
            athlete_id=athlete_id,
            lookback_days=lookback_days,
            max_activities=max_activities,
            batch_size=10,
            per_page=200,
        )

        if not result or result.get("fetched", 0) == 0:
            logger.info(f"📭 No activities fetched for athlete_id={athlete_id}")
        else:
            logger.info(f"✅ Ingestion completed: {result}")

        return jsonify({"status": "success", "result": result}), 200

    except Exception as e:
        logger.exception(f"❌ Exception during ingestion for athlete_id={athlete_id}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        session.close()
