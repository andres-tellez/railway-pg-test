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

from __future__ import annotations

import os
import traceback
from typing import Optional

from flask import Blueprint, jsonify, request
from sqlalchemy import text

import src.utils.config as config
from src.db.db_session import get_session
from src.services.activity_service import ActivityIngestionService, run_enrichment_batch
from src.utils.auth0_jwt import requires_auth

activity_bp = Blueprint("activity", __name__)

# -------- Enrichment Routes --------


@requires_auth
@activity_bp.route("/enrich/status", methods=["GET"])
def enrich_status():
    """Quick health check."""
    return jsonify({"enrich": "ok"}), 200


@requires_auth
@activity_bp.route("/enrich/activity/<int:activity_id>", methods=["POST"])
def enrich_single(activity_id: int):
    """Trigger enrichment for a single activity."""
    session = get_session()
    try:
        row = session.execute(
            text("SELECT athlete_id FROM activities WHERE activity_id = :id"),
            {"id": activity_id},
        ).fetchone()

        if not row:
            return jsonify({"error": f"Activity {activity_id} not found"}), 404

        # SQLAlchemy Row supports attribute access for selected columns
        athlete_id = row.athlete_id  # type: ignore[attr-defined]

        service = ActivityIngestionService(session, athlete_id)
        service.enrich_single_activity(activity_id)

        return jsonify({"status": "ok", "activity_id": activity_id}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@requires_auth
@activity_bp.route("/enrich/batch", methods=["POST"])
def enrich_batch():
    """
    Enrich a batch of activities for a given athlete.

    Params (query string):
      - athlete_id: int (required)
      - batch: int (optional, default=20; clamped to [1, 500])
    """
    athlete_id: Optional[int] = request.args.get("athlete_id", type=int)
    batch: int = request.args.get("batch", default=20, type=int)

    if not athlete_id:
        return jsonify({"error": "Missing athlete_id"}), 400

    # Guardrails for batch size
    if batch is None or batch <= 0:
        batch = 20
    batch = max(1, min(batch, 500))

    session = get_session()
    try:
        enriched_count = run_enrichment_batch(session, athlete_id, batch_size=batch)
        return (
            jsonify(
                {
                    "status": "ok",
                    "athlete_id": athlete_id,
                    "batch_size": batch,
                    "enriched_count": int(enriched_count),
                }
            ),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# -------- Deprecated Sync Route --------


@requires_auth
@activity_bp.route("/sync/<int:athlete_id>")
def sync_strava_to_db(athlete_id: int):
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
        return (
            jsonify(
                {"inserted": int(inserted), "lookback_days": lookback, "limit": limit}
            ),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
