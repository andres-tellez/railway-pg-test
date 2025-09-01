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


@activity_bp.get("/api/activities/status")
@requires_auth
def activities_status():
    """Returns count of Strava activities for the current user."""
    from flask import g

    user_id = (getattr(g, "current_user", None) or {}).get("sub")
    session = get_session()
    try:
        count = session.execute(
            text("SELECT COUNT(*) FROM activities WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar()
        return jsonify({"recentActivitiesCount": int(count)}), 200
    except Exception:
        traceback.print_exc()
        return jsonify({"recentActivitiesCount": 0}), 200
    finally:
        session.close()


@activity_bp.post("/activities/sync")
@requires_auth
def activities_sync():
    """Triggers Strava sync for the current user."""
    from src.services.ingestion_orchestrator_service import (
        run_full_ingestion_and_enrichment,
    )

    session = get_session()
    try:
        from flask import g

        user_id = (getattr(g, "current_user", None) or {}).get("sub")
        result = run_full_ingestion_and_enrichment(
            session=session,
            athlete_id=user_id,
            lookback_days=None,
            max_activities=10,
            batch_size=10,
            per_page=200,
        )
        return jsonify({"ok": True, "fetched": result.get("fetched", 0)}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        session.close()


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
