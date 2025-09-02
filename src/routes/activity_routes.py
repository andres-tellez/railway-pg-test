# src/routes/activity_routes.py
from __future__ import annotations

import traceback
from typing import Optional

from flask import Blueprint, jsonify, request, g
from sqlalchemy import text

from src.db.db_session import get_session
from src.services.activity_service import ActivityIngestionService, run_enrichment_batch
from src.utils.auth0_jwt import requires_auth

# Mounted in app.py with:
#   app.register_blueprint(activity_bp, url_prefix="/api/activities")
activity_bp = Blueprint("activity", __name__)


@activity_bp.get("/status")
@requires_auth
def activities_status():
    """
    Return count of Strava activities for the current logged-in user.
    Resolves user -> athlete via user_athletes mapping.
    """
    user_id = (getattr(g, "current_user", None) or {}).get("sub")
    session = get_session()
    try:
        sql = text(
            """
            SELECT COUNT(*)
            FROM activities a
            WHERE a.athlete_id IN (
                SELECT ua.athlete_id
                FROM user_athletes ua
                WHERE ua.user_id = :uid
            )
            """
        )
        count = session.execute(sql, {"uid": user_id}).scalar() or 0
        return jsonify({"recentActivitiesCount": int(count)}), 200
    except Exception:
        traceback.print_exc()
        return jsonify({"recentActivitiesCount": 0}), 200
    finally:
        session.close()


@activity_bp.post("/sync")
@requires_auth
def activities_sync():
    """
    Trigger Strava sync for the current user (dev only – safe no-op if not linked).
    """
    from src.services.ingestion_orchestrator_service import (
        run_full_ingestion_and_enrichment,
    )

    session = get_session()
    try:
        user_id = (getattr(g, "current_user", None) or {}).get("sub")

        # Resolve athlete_id from mapping table
        row = session.execute(
            text("SELECT athlete_id FROM user_athletes WHERE user_id = :uid LIMIT 1"),
            {"uid": user_id},
        ).fetchone()
        if not row:
            return jsonify({"ok": True, "fetched": 0, "note": "no athlete linked"}), 200

        athlete_id = row.athlete_id  # type: ignore[attr-defined]

        result = run_full_ingestion_and_enrichment(
            session=session,
            athlete_id=athlete_id,
            lookback_days=None,
            max_activities=10,
            batch_size=10,
            per_page=200,
        )
        return jsonify({"ok": True, "fetched": int(result.get("fetched", 0))}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        session.close()


# -------- Enrichment routes --------


@activity_bp.get("/enrich/status")
@requires_auth
def enrich_status():
    return jsonify({"enrich": "ok"}), 200


@activity_bp.post("/enrich/activity/<int:activity_id>")
@requires_auth
def enrich_single(activity_id: int):
    session = get_session()
    try:
        row = session.execute(
            text("SELECT athlete_id FROM activities WHERE activity_id = :id"),
            {"id": activity_id},
        ).fetchone()
        if not row:
            return jsonify({"error": f"Activity {activity_id} not found"}), 404

        athlete_id = row.athlete_id  # type: ignore[attr-defined]
        service = ActivityIngestionService(session, athlete_id)
        service.enrich_single_activity(activity_id)
        return jsonify({"status": "ok", "activity_id": activity_id}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@activity_bp.post("/enrich/batch")
@requires_auth
def enrich_batch():
    athlete_id: Optional[int] = request.args.get("athlete_id", type=int)
    batch: int = request.args.get("batch", default=20, type=int)

    if not athlete_id:
        return jsonify({"error": "Missing athlete_id"}), 400

    batch = max(1, min(batch or 20, 500))

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
