from __future__ import annotations

import traceback
from typing import Optional

from flask import Blueprint, jsonify, request, g
from sqlalchemy import text

from src.db.db_session import get_session
from src.services.activity_service import ActivityIngestionService, run_enrichment_batch
from src.utils.auth0_jwt import requires_auth

activity_bp = Blueprint("activity", __name__)


@activity_bp.get("/status")
@requires_auth
def activities_status():
    """
    Return count of Strava activities and connection status for current logged-in user.
    Resolves user -> athlete via user_athletes mapping.
    Falls back to the athlete_id with most activities if current mapping is invalid.
    """
    user_id = (getattr(g, "current_user", None) or {}).get("sub")
    session = get_session()
    try:
        athlete_row = session.execute(
            text("SELECT athlete_id FROM user_athletes WHERE user_id = :uid LIMIT 1"),
            {"uid": user_id},
        ).fetchone()

        is_connected = athlete_row is not None
        athlete_id = athlete_row.athlete_id if is_connected else None

        print(f"👤 user_id = {user_id}")
        print(f"🔍 athlete_row = {athlete_row}")
        print(f"🏃 original athlete_id = {athlete_id}")

        # 🧠 Fallback: If no activities are found for this athlete_id, try another
        if athlete_id:
            row_exists = session.execute(
                text("SELECT 1 FROM activities WHERE athlete_id = :aid LIMIT 1"),
                {"aid": athlete_id},
            ).fetchone()

            if not row_exists:
                fallback = session.execute(
                    text(
                        "SELECT athlete_id FROM activities GROUP BY athlete_id ORDER BY COUNT(*) DESC LIMIT 1"
                    )
                ).fetchone()
                if fallback:
                    print(f"⏭ Fallback to athlete_id = {fallback.athlete_id}")
                    athlete_id = fallback.athlete_id

        count = (
            (
                session.execute(
                    text("SELECT COUNT(*) FROM activities WHERE athlete_id = :aid"),
                    {"aid": athlete_id},
                ).scalar()
                or 0
            )
            if athlete_id
            else 0
        )

        status = "Complete" if count >= 9 else "Pending"
        print(f"📊 Returning activity status: {count} activities → {status}")

        return (
            jsonify(
                {
                    "stravaConnected": is_connected,
                    "recentActivitiesCount": int(count),
                    "status": status,
                }
            ),
            200,
        )

    except Exception:
        traceback.print_exc()
        return jsonify({"stravaConnected": False, "recentActivitiesCount": 0}), 200
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
        print("🆕 Sync route triggered for user:", user_id)

        # Resolve current athlete mapping
        mapping_row = session.execute(
            text("SELECT athlete_id FROM user_athletes WHERE user_id = :uid LIMIT 1"),
            {"uid": user_id},
        ).fetchone()

        current_athlete_id = mapping_row.athlete_id if mapping_row else None

        # 🧠 Attempt to auto-correct mapping if broken
        if current_athlete_id is not None:
            real_athlete_id_row = session.execute(
                text(
                    """
                    SELECT athlete_id
                    FROM activities
                    WHERE athlete_id = :aid
                    LIMIT 1
                """
                ),
                {"aid": current_athlete_id},
            ).fetchone()

            if not real_athlete_id_row:
                print(
                    f"⚠️ Mapped athlete_id {current_athlete_id} has no activities. Searching for actual athlete..."
                )
                actual_row = session.execute(
                    text(
                        """
                        SELECT athlete_id
                        FROM activities
                        GROUP BY athlete_id
                        ORDER BY COUNT(*) DESC
                        LIMIT 1
                    """
                    )
                ).fetchone()

                if actual_row:
                    print(
                        f"✅ Found better athlete_id: {actual_row.athlete_id} → Updating mapping..."
                    )
                    session.execute(
                        text(
                            """
                            INSERT INTO user_athletes (user_id, athlete_id)
                            VALUES (:uid, :aid)
                            ON CONFLICT (user_id) DO UPDATE SET athlete_id = EXCLUDED.athlete_id
                        """
                        ),
                        {"uid": user_id, "aid": actual_row.athlete_id},
                    )
                    session.commit()
                    session.expire_all()
                    current_athlete_id = actual_row.athlete_id

        # ✅ Pull strava_athlete_id from athletes table
        # ✅ Correctly map strava_athlete_id if missing or stale
        strava_row = session.execute(
            text(
                """
                SELECT id, strava_athlete_id
                FROM athletes
                WHERE strava_athlete_id = (
                    SELECT strava_athlete_id FROM athletes WHERE id = :id
                )
                LIMIT 1
                """
            ),
            {"id": current_athlete_id},
        ).fetchone()

        if not strava_row:
            return jsonify({"ok": False, "error": "Strava athlete not found"}), 404

        # 🧠 Ensure mapping is using correct internal athlete_id
        if strava_row.id != current_athlete_id:
            print(
                f"🔁 Updating athlete mapping from {current_athlete_id} → {strava_row.id}"
            )
            session.execute(
                text(
                    """
                    INSERT INTO user_athletes (user_id, athlete_id)
                    VALUES (:uid, :aid)
                    ON CONFLICT (user_id) DO UPDATE SET athlete_id = EXCLUDED.athlete_id
                """
                ),
                {"uid": user_id, "aid": strava_row.id},
            )
            session.commit()
            session.expire_all()

        strava_athlete_id = strava_row.strava_athlete_id  # ✅ used for ingestion

        if not strava_row:
            return jsonify({"ok": False, "error": "Strava athlete not found"}), 404

        strava_athlete_id = strava_row.strava_athlete_id

        # ✅ Correct: Pass strava_athlete_id here
        result = run_full_ingestion_and_enrichment(
            session=session,
            athlete_id=strava_athlete_id,
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
