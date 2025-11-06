"""
Activity Routes Module
======================

Provides API endpoints for managing and enriching user activities.

Endpoints:
----------
GET  /api/activities/
    Get user's activities (last 30 days) for plan generation context

GET  /api/activities/status
    Get Strava connection status and activity sync progress

GET  /api/activities/enrich/status
    Check enrichment service status

POST /api/activities/enrich/activity/<activity_id>
    Enrich a single activity with additional data

POST /api/activities/enrich/batch
    Enrich a batch of activities for an athlete

Dependencies:
-------------
- ActivityIngestionService: Activity enrichment logic
- requires_auth: JWT authentication decorator
- Database: activities table, user_athletes table

Data Source:
-----------
- activities table: Stores synced Strava activities
- Enrichment: Adds calculated metrics (pace zones, HR zones, etc.)
"""

from __future__ import annotations

import traceback
from typing import Optional

from flask import Blueprint, jsonify, request, g
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import UUID

from src.db.db_session import get_session
from src.services.activity_service import ActivityIngestionService, run_enrichment_batch
from src.utils.auth0_jwt import requires_auth
from src.utils.config import config

activity_bp = Blueprint("activity", __name__, url_prefix="/api/activities")


@activity_bp.get("/")
@requires_auth
def get_activities():
    """
    Return user's activities for plan generation context.
    Returns basic activity data with distances and dates.
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            return jsonify({"activities": []}), 200

        # Get athlete_id for this user
        stmt = text(
            """
            SELECT athlete_id
            FROM public.user_athletes
            WHERE user_id = :uid
            LIMIT 1
            """
        ).bindparams(bindparam("uid", type_=UUID))
        athlete_row = session.execute(stmt, {"uid": internal_user_id}).fetchone()

        if not athlete_row:
            return jsonify({"activities": []}), 200

        athlete_id = athlete_row.athlete_id

        # Fetch activities from the last 30 days (4 weeks)
        activities_stmt = text(
            """
            SELECT
                activity_id,
                start_date,
                distance,
                moving_time,
                name,
                type
            FROM public.activities
            WHERE athlete_id = :aid
            AND start_date >= NOW() - INTERVAL '30 days'
            ORDER BY start_date DESC
            """
        )

        activities_result = session.execute(
            activities_stmt, {"aid": athlete_id}
        ).fetchall()

        activities = [
            {
                "activity_id": row[0],
                "date": row[1].isoformat() if row[1] else None,
                "distance_miles": (
                    float(row[2] * 0.000621371) if row[2] else 0
                ),  # Convert meters to miles
                "moving_time": row[3],
                "name": row[4],
                "type": row[5],
            }
            for row in activities_result
        ]

        return jsonify({"activities": activities}), 200

    except Exception as e:
        print(f"❌ Error fetching activities: {e}")
        traceback.print_exc()
        return jsonify({"activities": []}), 200
    finally:
        session.close()


@activity_bp.get("/status")
@requires_auth
def activities_status():
    """
    Return Strava connection status + progress of synced activities for current user.
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            print("❌ No internal_user_id on g")
            return (
                jsonify(
                    {
                        "stravaConnected": False,
                        "downloaded": 0,
                        "total": config.MIN_ACTIVITIES_REQUIRED,
                        "status": "Pending",
                    }
                ),
                200,
            )

        # 🔗 Resolve athlete mapping
        stmt = text(
            """
            SELECT athlete_id
            FROM public.user_athletes
            WHERE user_id = :uid
            LIMIT 1
            """
        ).bindparams(bindparam("uid", type_=UUID))
        athlete_row = session.execute(stmt, {"uid": internal_user_id}).fetchone()

        is_connected = athlete_row is not None
        athlete_id = athlete_row.athlete_id if is_connected else None

        # 🧠 fallback: busiest athlete
        if athlete_id:
            row_exists = session.execute(
                text("SELECT 1 FROM public.activities WHERE athlete_id = :aid LIMIT 1"),
                {"aid": athlete_id},
            ).fetchone()
            if not row_exists:
                fallback = session.execute(
                    text(
                        """
                        SELECT athlete_id
                        FROM public.activities
                        GROUP BY athlete_id
                        ORDER BY COUNT(*) DESC
                        LIMIT 1
                        """
                    )
                ).fetchone()
                if fallback:
                    print(f"⏭ Fallback to athlete_id = {fallback.athlete_id}")
                    athlete_id = fallback.athlete_id

        # 📊 Count activities
        count = (
            (
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM public.activities WHERE athlete_id = :aid"
                    ),
                    {"aid": athlete_id},
                ).scalar()
                or 0
            )
            if athlete_id
            else 0
        )

        total = config.MIN_ACTIVITIES_REQUIRED
        status = "Complete" if count >= total else "Syncing" if count > 0 else "Pending"

        print(f"📊 Returning activity status: {count}/{total} → {status}")

        return (
            jsonify(
                {
                    "stravaConnected": is_connected,
                    "downloaded": int(count),
                    "total": total,
                    "status": status,
                }
            ),
            200,
        )

    except Exception:
        traceback.print_exc()
        return (
            jsonify(
                {
                    "stravaConnected": False,
                    "downloaded": 0,
                    "total": config.MIN_ACTIVITIES_REQUIRED,
                    "status": "Pending",
                }
            ),
            200,
        )
    finally:
        session.close()


# Deprecated sync route removed - use /api/progress/ingest instead


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
