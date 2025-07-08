from flask import Blueprint, jsonify, request
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment
from src.db.db_session import get_session

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/ping")
def ping():
    return "pong from admin"

@admin_bp.route("/trigger-ingest/<int:athlete_id>", methods=["POST"])
def trigger_ingestion(athlete_id):
    print(f"⏱️ Received trigger-ingest for athlete {athlete_id}", flush=True)
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
            per_page=200
)
        print(f"✅ Ingestion result: {result}", flush=True)
        return jsonify({"status": "success", "result": result}), 200
    except Exception as e:
        print(f"❌ Ingestion error: {e}", flush=True)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()
