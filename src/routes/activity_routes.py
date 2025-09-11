from __future__ import annotations

import os

import traceback
from typing import Optional

from flask import Blueprint, jsonify, request, g
from sqlalchemy import text

from src.db.db_session import get_session
from src.services.activity_service import ActivityIngestionService, run_enrichment_batch
from src.utils.auth0_jwt import requires_auth

from sqlalchemy.exc import ProgrammingError

activity_bp = Blueprint("activity", __name__)

from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import UUID


@activity_bp.get("/status")
@requires_auth
def activities_status():
    """
    Return count of Strava activities and connection status for the current user.
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)  # ✅ resolved in requires_auth
        sub = getattr(g, "current_user", {}).get("sub")

        if not internal_user_id:
            print("❌ No internal_user_id on g")
            return jsonify({"stravaConnected": False, "recentActivitiesCount": 0}), 200

        # 🔗 Resolve athlete mapping using the UUID
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

        print(f"👤 sub = {sub}")
        print(f"🔐 internal_user_id = {internal_user_id}")
        print(f"🔍 athlete_row = {athlete_row}")
        print(f"🏃 original athlete_id = {athlete_id}")

        # 🧠 Fallback: if mapped athlete has no activities, use the busiest athlete
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
    Trigger Strava sync for the current user.
    Resolves internal user_id → athlete_id → tokens → refresh if needed → calls Strava API.
    """
    import requests
    from datetime import datetime
    from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa
    from src.services.ingestion_orchestrator_service import (
        run_full_ingestion_and_enrichment,
    )

    STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")

    session = get_session()
    try:
        sub = (getattr(g, "current_user", None) or {}).get("sub")
        print("🆕 Sync route triggered for sub:", sub)

        # ✅ Already resolved by requires_auth
        internal_user_id = getattr(g, "user_id", None)
        if not internal_user_id:
            return jsonify({"ok": False, "error": "User mapping not found"}), 404

        # 🔗 Step 2: Resolve user_id → athlete_id
        mapping_row = session.execute(
            text(
                """
                SELECT athlete_id
                FROM public.user_athletes
                WHERE user_id = :uid
                LIMIT 1
                """
            ),
            {"uid": internal_user_id},
        ).fetchone()
        if not mapping_row:
            return jsonify({"ok": False, "error": "No athlete linked"}), 404

        athlete_id = mapping_row.athlete_id
        print(f"✅ Resolved athlete_id={athlete_id}")

        # 🔑 Step 3: Fetch Strava tokens
        tokens = get_tokens_sa(session, athlete_id)
        if not tokens or not tokens.get("access_token"):
            return jsonify({"ok": False, "error": "Access token not found"}), 401

        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        expires_at = tokens.get("expires_at")  # unix timestamp

        # 🔄 Step 3b: Refresh if expired
        now_ts = int(datetime.utcnow().timestamp())
        if expires_at and now_ts >= expires_at - 60:
            print("🔄 Access token expired → refreshing...")
            refresh_resp = requests.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": STRAVA_CLIENT_ID,
                    "client_secret": STRAVA_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                timeout=10,
            )
            if refresh_resp.status_code != 200:
                return jsonify({"ok": False, "error": "Failed to refresh token"}), 401

            new_tokens = refresh_resp.json()
            access_token = new_tokens["access_token"]
            refresh_token = new_tokens["refresh_token"]
            expires_at = new_tokens["expires_at"]

            # Save new tokens
            save_tokens_sa(
                session,
                athlete_id,
                access_token,
                refresh_token,
                expires_at,
            )
            session.commit()
            print("✅ Token refreshed and saved")

        print(f"🔑 Using Strava access_token (len={len(access_token)})")

        # 🚴 Step 4: Call Strava API to fetch activities
        resp = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"per_page": 10, "page": 1},
            timeout=10,
        )

        print(f"📡 Strava API response {resp.status_code}: {resp.text[:200]}")

        if resp.status_code == 401:
            return jsonify({"ok": False, "error": "Invalid or expired token"}), 401
        elif resp.status_code != 200:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"Strava API failed ({resp.status_code})",
                        "body": resp.text[:200],
                    }
                ),
                502,
            )

        activities = resp.json()
        print(f"📥 Retrieved {len(activities)} activities from Strava")

        # 🧠 Step 5: Save into DB (via ingestion service)
        result = run_full_ingestion_and_enrichment(
            session=session,
            athlete_id=athlete_id,
            max_activities=10,
            batch_size=10,
            per_page=200,
        )

        return (
            jsonify(
                {"ok": True, "fetched": int(result.get("fetched", len(activities)))}
            ),
            200,
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        session.close()


# src/routes/activity_routes.py
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

# ...existing imports...


def _resolve_internal_user_id(session, sub: str) -> str | None:
    row = session.execute(
        text(
            """
            SELECT user_id
            FROM public.user_auth_providers
            WHERE provider_user_id = :sub
            LIMIT 1
        """
        ),
        {"sub": sub},
    ).fetchone()
    return row.user_id if row else None


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
