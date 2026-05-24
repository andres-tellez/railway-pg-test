"""
Admin Routes Module
===================

Provides administrative and debugging endpoints for system management.

Endpoints:
----------
GET  /admin/ping
    Basic health check endpoint

GET/POST /admin/test-no-auth
    Test endpoint without authentication (for debugging)

POST /admin/refresh-metrics
    Manually trigger metrics refresh

POST /admin/refresh-weekly-training-insights
    Recompute weekly_training_insights for six completed weeks and current week

POST /admin/trigger-ingest/<athlete_id>
    Manually trigger activity ingestion for an athlete

POST /admin/fetch-activity/<activity_id>
    Manually fetch a single activity from Strava

GET  /admin/athletes
    Get list of all athletes for admin dropdown (requires auth)

POST /admin/delete-user
    Permanently delete a user account by internal user_id (admin only; Strava athlete 347085)

POST /admin/sync-activities
    Sync activities for a specific athlete in a date range

Dependencies:
-------------
- ActivityIngestionService: Activity ingestion logic
- StravaClient: Strava API access
- TokenService: Token management
- requires_auth: JWT authentication decorator

Note:
-----
These endpoints are for administrative use and debugging.
All endpoints require authentication unless otherwise specified.
"""

from flask import Blueprint, jsonify, request
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from src.db.db_session import get_session
from src.services.strava_access_service import StravaClient
from src.services.token_service import get_valid_token
from src.db.dao.activity_dao import ActivityDAO
from src.db.dao.user_identity_dao import persist_splits_for_user
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.user_identity import UserIdentity
import logging
import uuid
from src.utils.auth0_jwt import requires_auth
from src.utils.authorization import is_admin
from src.services.user_account_deletion_service import delete_all_user_account_data

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
logger = logging.getLogger(__name__)

# Force print at module level to confirm blueprint loads
print("[ADMIN_BLUEPRINT] Module loaded successfully", flush=True)


@admin_bp.before_request
def log_admin_requests():
    """Log all requests to admin routes for debugging."""
    print(f"[ADMIN_BEFORE_REQUEST] {request.method} {request.path}", flush=True)
    logger.info(f"[ADMIN] {request.method} {request.path}")


@admin_bp.route("/ping")
def ping():
    return "pong from admin"


@admin_bp.route("/test-no-auth", methods=["GET", "POST"])
def test_no_auth():
    """Test endpoint without auth to debug routing."""
    print("✅ [TEST-NO-AUTH] This endpoint was hit!", flush=True)
    logger.info("✅ [TEST-NO-AUTH] This endpoint was hit!")
    return jsonify({"status": "success", "message": "Admin routes are working"}), 200


@admin_bp.route("/refresh-metrics", methods=["POST"])
@requires_auth
def refresh_metrics():
    """Manually trigger the metrics refresh."""
    print("🔴 [REFRESH-METRICS] Function entered!", flush=True)

    import sys
    import logging

    # Force refresh_metrics_cron logger to output to stdout
    refresh_logger = logging.getLogger("src.scripts.refresh_metrics_cron")
    if not refresh_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        refresh_logger.addHandler(handler)
        refresh_logger.setLevel(logging.INFO)

    logger.info("🔄 [Manual Trigger] Starting metrics refresh...")

    try:
        from src.scripts.refresh_metrics_cron import main as refresh_main

        exit_code = refresh_main()

        if exit_code == 0:
            logger.info("✅ Metrics refresh completed successfully")
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Metrics refreshed successfully",
                    }
                ),
                200,
            )
        else:
            logger.error("❌ Metrics refresh completed with errors")
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Metrics refresh completed with errors",
                    }
                ),
                500,
            )
    except Exception as e:
        print(f"🔴 [REFRESH-METRICS] Exception: {e}", flush=True)
        logger.exception(f"❌ Exception during metrics refresh: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route("/refresh-weekly-training-insights", methods=["POST"])
@requires_auth
def refresh_weekly_training_insights():
    """
    Batch-refresh ``weekly_training_insights`` for the mobile Insights tab.

    Runs (1) six completed Mon–Sun weeks (oldest → newest) and (2) current calendar week
    (``in_progress``) for users with easy runs in each window.
    """
    session = get_session()
    try:
        from src.services.admin_weekly_insights_batch_service import (
            run_weekly_insights_admin_batch,
        )

        payload = run_weekly_insights_admin_batch(session)
        err_c = payload["six_completed_weeks"]["totals"].get("errors", 0)
        err_p = payload["current_week_in_progress"].get("errors", 0)
        if err_c or err_p:
            payload["status"] = "partial"
        else:
            payload["status"] = "success"
        return jsonify(payload), 200
    except Exception as e:
        logger.exception("refresh_weekly_training_insights failed: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()


# Legacy endpoints - kept for backward compatibility but deprecated
@admin_bp.route("/trigger-ingest/<int:athlete_id>", methods=["POST"])
@requires_auth
def trigger_ingestion(athlete_id):
    """DEPRECATED: Use /admin/sync-activities instead."""
    logger.warning(
        f"⚠️ [DEPRECATED] /trigger-ingest endpoint used. Use /admin/sync-activities instead."
    )
    # Redirect to unified endpoint by calling sync_activities with appropriate data
    original_json = request.get_json()
    request._cached_json = {
        **(original_json or {}),
        "athlete_id": athlete_id,
        "lookback_days": request.args.get("lookback_days", default=None, type=int),
        "max_activities": request.args.get("max_activities", default=10, type=int),
    }
    return sync_activities()


@admin_bp.route("/fetch-activity/<int:activity_id>", methods=["POST"])
@requires_auth
def fetch_single_activity(activity_id):
    """DEPRECATED: Use /admin/sync-activities with activity_id instead."""
    logger.warning(
        f"⚠️ [DEPRECATED] /fetch-activity endpoint used. Use /admin/sync-activities instead."
    )
    # Redirect to unified endpoint by calling sync_activities with appropriate data
    original_json = request.get_json()
    request._cached_json = {
        **(original_json or {}),
        "activity_id": activity_id,
        "athlete_id": request.args.get("athlete_id", type=int),
    }
    return sync_activities()


@admin_bp.route("/athletes")
@requires_auth
def get_athletes():
    """Get list of all athletes for admin dropdown (name + athlete_id + internal user_id)."""
    session = get_session()
    try:
        links = session.query(UserAthleteLink).all()
        uid_strings = [str(link.user_id) for link in links]
        uuid_list = []
        for s in uid_strings:
            try:
                uuid_list.append(uuid.UUID(s))
            except ValueError:
                continue
        identities = (
            session.query(UserIdentity)
            .filter(UserIdentity.user_id.in_(uuid_list))
            .all()
            if uuid_list
            else []
        )
        by_user_id = {str(row.user_id): row for row in identities}

        athlete_list = []
        for link in links:
            uid = str(link.user_id)
            ident = by_user_id.get(uid)
            name = (ident.name or "").strip() if ident else ""
            email = (ident.email or "").strip() if ident else ""
            label = name or email or "Unknown"
            athlete_list.append(
                {
                    "athlete_id": link.athlete_id,
                    "user_id": uid,
                    "user_name": name or None,
                    "email": email or None,
                    "display_name": label,
                }
            )
        return jsonify({"athletes": athlete_list}), 200
    except Exception as e:
        logger.exception(f"❌ Failed to fetch athletes")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()


@admin_bp.route("/delete-user", methods=["POST"])
@requires_auth
def admin_delete_user():
    """
    Permanently delete another user's account (internal user_id).

    Requires is_admin(): caller must be linked to Strava athlete_id 347085 in user_athletes.
    Body: {"user_id": "<uuid>", "confirm": true}
    """
    from flask import g

    if not is_admin():
        return (
            jsonify(
                {
                    "error": "Admin access required",
                    "hint": "Only the SmartCoach user linked to Strava athlete_id 347085 may delete other accounts.",
                }
            ),
            403,
        )

    payload = request.get_json(silent=True) or {}
    target_user_id = (payload.get("user_id") or "").strip()
    if payload.get("confirm") is not True:
        return jsonify({"error": "confirm must be true"}), 400
    if not target_user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        uuid.UUID(target_user_id)
    except ValueError:
        return jsonify({"error": "user_id must be a valid UUID"}), 400

    actor = str(getattr(g, "user_id", "") or "")
    if actor and actor == target_user_id:
        return (
            jsonify(
                {
                    "error": "Refusing to delete your own account via admin; use account settings / GDPR delete.",
                }
            ),
            400,
        )

    session = get_session()
    try:
        exists = (
            session.query(UserIdentity)
            .filter_by(user_id=uuid.UUID(target_user_id))
            .first()
        )
        if not exists:
            return jsonify({"error": "User not found"}), 404

        deletions = delete_all_user_account_data(session, target_user_id)
        session.commit()
        logger.warning(
            "Admin delete-user: actor=%s deleted user_id=%s summary=%s",
            actor,
            target_user_id,
            deletions,
        )
        return (
            jsonify(
                {
                    "success": True,
                    "message": "User account permanently deleted",
                    "deleted": deletions,
                }
            ),
            200,
        )
    except Exception as e:
        session.rollback()
        logger.exception("admin_delete_user failed: %s", e)
        return jsonify({"error": "Failed to delete user", "detail": str(e)}), 500
    finally:
        session.close()


@admin_bp.route("/sync-activities", methods=["POST"])
@requires_auth
def sync_activities():
    """
    Unified endpoint for syncing and enriching activities.

    Supports three modes:
    1. Single activity fetch: Provide 'activity_id' (and optionally 'athlete_id')
    2. Date range sync: Provide 'athlete_id', 'start_date', 'end_date'
    3. Full ingestion: Provide 'athlete_id' and optionally 'lookback_days', 'max_activities'

    All modes will enrich activities after fetching.

    Request body (JSON):
        - activity_id (int, optional): Fetch and enrich a single activity
        - athlete_id (int, required): Strava athlete ID
        - start_date (str, optional): Start date in YYYY-MM-DD format
        - end_date (str, optional): End date in YYYY-MM-DD format
        - lookback_days (int, optional): Days to look back for full sync
        - max_activities (int, optional): Maximum activities to fetch

    Examples:
        # Single activity
        POST /admin/sync-activities
        {"activity_id": 12345678, "athlete_id": 347085}

        # Date range
        POST /admin/sync-activities
        {"athlete_id": 347085, "start_date": "2025-10-01", "end_date": "2025-10-31"}

        # Full ingestion
        POST /admin/sync-activities
        {"athlete_id": 347085, "lookback_days": 30, "max_activities": 50}
    """
    logger.info("🔄 [Sync Activities] Unified sync request received")
    session = get_session()

    try:
        # Get user_id from authenticated user
        from flask import g

        user_id = getattr(g, "user_id", None)
        if user_id:
            logger.info(f"✅ [Sync Activities] Authenticated user_id={user_id}")

        data = request.get_json() or {}
        activity_id = data.get("activity_id")
        athlete_id = data.get("athlete_id")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        lookback_days = data.get("lookback_days")
        max_activities = data.get("max_activities", 10)

        logger.info(
            f"🔄 [Sync Activities] activity_id={activity_id}, athlete_id={athlete_id}, "
            f"start_date={start_date}, end_date={end_date}, lookback_days={lookback_days}"
        )

        # MODE 1: Single activity fetch
        if activity_id:
            if not athlete_id:
                # Try to get athlete_id from authenticated user
                if user_id:
                    mapping = (
                        session.query(UserAthleteLink)
                        .filter_by(user_id=user_id)
                        .first()
                    )
                    if mapping:
                        athlete_id = mapping.athlete_id
                        logger.info(
                            f"✅ Auto-detected athlete_id={athlete_id} for user_id={user_id}"
                        )

            if not athlete_id:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "athlete_id required when fetching single activity",
                        }
                    ),
                    400,
                )

            # Get valid Strava access token
            access_token = get_valid_token(session, athlete_id)
            if not access_token:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"No valid token for athlete {athlete_id}",
                        }
                    ),
                    401,
                )

            # Fetch activity from Strava
            logger.info(f"📥 Fetching activity {activity_id} from Strava API...")
            client = StravaClient(access_token)
            activity_data = client.get_activity(activity_id)

            if not activity_data:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"Failed to fetch activity {activity_id} from Strava",
                        }
                    ),
                    404,
                )

            # Check if it's a run
            activity_type = activity_data.get("type")
            if activity_type != "Run":
                logger.info(
                    f"ℹ️ Activity {activity_id} is type '{activity_type}', not a run"
                )
                return (
                    jsonify(
                        {
                            "status": "skipped",
                            "message": f"Activity is type '{activity_type}', not a run",
                            "activity_type": activity_type,
                        }
                    ),
                    200,
                )

            # Get user_id for this athlete
            mapping = (
                session.query(UserAthleteLink).filter_by(athlete_id=athlete_id).first()
            )
            if not mapping:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"No user mapping found for athlete {athlete_id}",
                        }
                    ),
                    404,
                )

            user_id = mapping.user_id

            # Prepare and store activity
            activity_data["activity_id"] = activity_data.pop("id", activity_id)
            activity_data["user_id"] = user_id

            inserted = ActivityDAO.upsert_activities(
                session, athlete_id, [activity_data], user_id=user_id
            )

            if inserted > 0:
                logger.info(f"✅ Successfully stored activity {activity_id}")
            else:
                logger.info(f"ℹ️ Activity {activity_id} already exists, will enrich")

            # ENRICH the activity (this is the key fix!)
            try:
                from src.services.activity_service import (
                    enrich_one_activity_with_refresh,
                )

                persist_splits = persist_splits_for_user(session, user_id)
                enrich_one_activity_with_refresh(
                    session,
                    athlete_id,
                    activity_id,
                    fetch_streams=True,
                    persist_splits=persist_splits,
                )
                logger.info(f"✅ Successfully enriched activity {activity_id}")
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to enrich activity {activity_id}: {e}", exc_info=True
                )
                # Don't fail the request if enrichment fails, but log it

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": f"Activity {activity_id} fetched and enriched",
                        "activity_id": activity_id,
                        "activity_type": activity_type,
                        "name": activity_data.get("name"),
                        "distance": activity_data.get("distance"),
                        "moving_time": activity_data.get("moving_time"),
                    }
                ),
                200,
            )

        # MODE 2 & 3: Date range sync or full ingestion
        if not athlete_id:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "athlete_id is required",
                    }
                ),
                400,
            )

        # Ingestion must use the Strava-linked account owner, not only the admin JWT user,
        # so sync_status / retries / activity.user_id stay consistent.
        owner_link = (
            session.query(UserAthleteLink).filter_by(athlete_id=athlete_id).first()
        )
        ingestion_user_id = str(owner_link.user_id) if owner_link else None
        if not ingestion_user_id:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": (
                            f"No user linked to Strava athlete_id={athlete_id}. "
                            "That account must connect Strava before activities can be synced."
                        ),
                    }
                ),
                404,
            )

        actor_user_id = str(user_id) if user_id else None
        if actor_user_id and actor_user_id != ingestion_user_id:
            logger.info(
                "🔄 [Sync Activities] Admin actor=%s running sync for athlete %s (owner user_id=%s)",
                actor_user_id,
                athlete_id,
                ingestion_user_id,
            )

        # MODE 2: Date range sync
        if start_date and end_date:
            # Convert dates to Unix timestamps (UTC)
            from datetime import datetime, timezone, time as dt_time

            try:
                # Parse dates and set to start of day UTC
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                start_timestamp = int(start_dt.timestamp())

                # For end date, set to end of day (23:59:59) UTC
                end_dt = datetime.combine(
                    datetime.strptime(end_date, "%Y-%m-%d").date(),
                    dt_time.max,
                    tzinfo=timezone.utc,
                )
                end_timestamp = int(end_dt.timestamp())

                logger.info(
                    f"🔄 [Sync Activities] Date conversion: "
                    f"start_date={start_date} -> {start_dt.isoformat()} (timestamp={start_timestamp}), "
                    f"end_date={end_date} -> {end_dt.isoformat()} (timestamp={end_timestamp})"
                )
            except ValueError as e:
                logger.warning(f"⚠️ [Sync Activities] Invalid date format: {e}")
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"Invalid date format. Use YYYY-MM-DD format. Error: {str(e)}",
                        }
                    ),
                    400,
                )

            logger.info(
                f"🔄 [Sync Activities] Starting background sync for athlete {athlete_id} "
                f"from {start_date} to {end_date} (UTC timestamps: {start_timestamp} to {end_timestamp})"
            )

            # Run sync in background job (don't block HTTP request)
            from src.utils.strava_helpers import run_background_job

            def sync_job(session, athlete_id, user_id, start_timestamp, end_timestamp):
                """Run sync in background thread"""
                import sys

                user_id_str = str(user_id) if user_id else None
                print(
                    f"🔄 [Background Sync] Starting sync for athlete {athlete_id}, "
                    f"user {user_id_str}, after={start_timestamp}, before={end_timestamp}",
                    file=sys.stdout,
                    flush=True,
                )
                logger.info(
                    f"🔄 [Background Sync] Starting sync for athlete {athlete_id}, user {user_id_str}, "
                    f"after={start_timestamp}, before={end_timestamp}"
                )
                try:
                    print(
                        f"🔄 [Background Sync] Calling run_full_ingestion_and_enrichment...",
                        file=sys.stdout,
                        flush=True,
                    )
                    logger.info(
                        f"🔄 [Background Sync] Calling run_full_ingestion_and_enrichment..."
                    )
                    result = run_full_ingestion_and_enrichment(
                        _unused_session=None,
                        athlete_id=athlete_id,
                        user_id=user_id_str,
                        after=start_timestamp,
                        before=end_timestamp,
                        max_activities=None,
                    )
                    print(
                        f"✅ [Background Sync] Sync completed: synced={result.get('synced', 0)}, "
                        f"enriched={result.get('enriched', 0)}",
                        file=sys.stdout,
                        flush=True,
                    )
                    logger.info(
                        f"✅ [Background Sync] Sync completed: synced={result.get('synced', 0)}, "
                        f"enriched={result.get('enriched', 0)}"
                    )
                    if result.get("deferred"):
                        logger.info(
                            "[Background Sync] Deferred (e.g. rate headroom); "
                            "new runs may be saved; enrichment will retry. result=%s",
                            result,
                        )
                    elif result.get("enriched", 0) == 0:
                        print(
                            f"⚠️ [Background Sync] No activities were enriched! Result: {result}",
                            file=sys.stdout,
                            flush=True,
                        )
                        logger.warning(
                            f"⚠️ [Background Sync] No activities were enriched! "
                            f"Result: {result}"
                        )
                except Exception as e:
                    print(
                        f"❌ [Background Sync] Sync failed: {e}",
                        file=sys.stderr,
                        flush=True,
                    )
                    logger.exception(f"❌ [Background Sync] Sync failed: {e}")

            logger.info(
                f"🚀 [Sync Activities] Launching background job for athlete {athlete_id}..."
            )
            run_background_job(
                sync_job,
                athlete_id,
                ingestion_user_id,
                start_timestamp,
                end_timestamp,
            )
            logger.info(
                f"✅ [Sync Activities] Background job launched, returning 202 response"
            )

            # Return immediately - sync is running in background
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": (
                            f"Sync queued for athlete {athlete_id} (owner user) from {start_date} to {end_date}. "
                            "Processing in the background; check deploy logs or strava_sync_status for completion."
                        ),
                        "athlete_id": athlete_id,
                        "date_range": f"{start_date} to {end_date}",
                    }
                ),
                202,  # 202 Accepted - request accepted but processing asynchronously
            )

        # MODE 3: Full ingestion
        logger.info(
            f"🔄 [Sync Activities] Starting full ingestion for athlete {athlete_id} "
            f"(lookback_days={lookback_days}, max_activities={max_activities})"
        )

        result = run_full_ingestion_and_enrichment(
            None,
            athlete_id,
            user_id=ingestion_user_id,
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
        logger.exception(f"❌ [Sync Activities] Failed to sync activities: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        session.close()


@admin_bp.route("/test-pace-calculation", methods=["POST"])
@requires_auth
def test_pace_calculation():
    """
    Test pace zone calculation for a user.

    Tests the performance-based pace calculation from recent run data.

    Request body (JSON):
        - user_id (str, optional): User UUID to test. If not provided, uses authenticated user.
        - week1_long (float, optional): Planned long run distance (default: 8.0)
        - lookback_weeks (int, optional): Weeks of history to analyze (default: 6)

    Returns:
        JSON response with calculated pace zones and calculation method used.
    """
    logger.info("🧪 [Test Pace Calculation] Request received")

    try:
        from flask import g
        from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi
        from src.smartcoach_mobile_coach.runner_profile.service import (
            get_runner_pace_zones_for_plan_generation,
        )

        data = request.get_json() or {}
        user_id = data.get("user_id") or getattr(g, "user_id", None)
        if not user_id:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "user_id required (or must be authenticated)",
                    }
                ),
                400,
            )

        user_id = str(user_id)
        lookback_weeks = int(data.get("lookback_weeks", 6))

        session = get_session()
        try:
            pace_zones = get_runner_pace_zones_for_plan_generation(
                session=session,
                user_id=user_id,
                force_refresh=True,
                lookback_weeks=lookback_weeks,
            )
            calculation_method = (
                "Calibration"
                if pace_zones.pace_source == "calibration"
                else "Performance-Based"
            )

            result = {
                "status": "success",
                "user_id": user_id,
                "calculation_method": calculation_method,
                "lookback_weeks": lookback_weeks,
                "pace_zones": {
                    "z2": {
                        "min_sec": int(pace_zones.pace_z2.low_sec),
                        "max_sec": int(pace_zones.pace_z2.high_sec),
                        "min": format_pace_sec_per_mi(
                            float(pace_zones.pace_z2.low_sec)
                        ),
                        "max": format_pace_sec_per_mi(
                            float(pace_zones.pace_z2.high_sec)
                        ),
                    },
                    "z3": {
                        "min_sec": int(pace_zones.pace_z3.low_sec),
                        "max_sec": int(pace_zones.pace_z3.high_sec),
                        "min": format_pace_sec_per_mi(
                            float(pace_zones.pace_z3.low_sec)
                        ),
                        "max": format_pace_sec_per_mi(
                            float(pace_zones.pace_z3.high_sec)
                        ),
                    },
                    "m": {
                        "sec": int(pace_zones.marathon_sec),
                        "pace": format_pace_sec_per_mi(float(pace_zones.marathon_sec)),
                    },
                    "z4": {
                        "min_sec": int(pace_zones.pace_z4.low_sec),
                        "max_sec": int(pace_zones.pace_z4.high_sec),
                        "min": format_pace_sec_per_mi(
                            float(pace_zones.pace_z4.low_sec)
                        ),
                        "max": format_pace_sec_per_mi(
                            float(pace_zones.pace_z4.high_sec)
                        ),
                    },
                },
                "week1_long_cap": round(float(pace_zones.week1_long_cap), 1),
            }
            return jsonify(result), 200
        finally:
            session.close()

    except Exception as e:
        logger.exception(f"❌ [Test Pace Calculation] Failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route("/update-current-week-pace", methods=["POST"])
@requires_auth
def update_current_week_pace():
    """
    Calculate new paces using performance-based method and rebuild current week.

    This endpoint:
    1. Calculates new pace zones from recent run performance (median easy pace)
    2. Rebuilds the current/upcoming week with the new paces
    3. Updates the plan in the database

    Request body (JSON, optional):
        - user_id (str, optional): User UUID. If not provided, uses authenticated user.
        - lookback_weeks (int, optional): Weeks of history to analyze (default: 6)

    Returns:
        JSON response with updated pace zones and rebuild status.
    """
    logger.info("🔄 [Update Current Week Pace] Request received")

    try:
        from flask import g
        from src.db.dao.plans_dao import get_active_plan
        from src.db.models.plans import Plan
        from src.smartcoach_mobile_coach.runner_profile.service import (
            get_runner_pace_zones_for_plan_generation,
        )
        from src.services.training_plan.weekly_rebuild_service import (
            WeeklyRebuildService,
        )
        from src.services.training_plan.week_log_service import fetch_week_logs
        from datetime import date

        data = request.get_json() or {}
        user_id = data.get("user_id")

        # Use authenticated user if no user_id provided
        if not user_id:
            user_id = getattr(g, "user_id", None)
            if not user_id:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "user_id required (or must be authenticated)",
                        }
                    ),
                    400,
                )

        user_id = str(user_id)
        lookback_weeks = data.get("lookback_weeks", 6)

        logger.info(
            f"🔄 [Update Current Week Pace] Processing for user_id={user_id}, "
            f"lookback_weeks={lookback_weeks}"
        )

        session = get_session()
        try:
            # 1. Get user's active plan
            plan = get_active_plan(session, user_id)
            if not plan:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "No active plan found for user",
                        }
                    ),
                    404,
                )

            if not plan.race_date:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Plan has no race date",
                        }
                    ),
                    400,
                )

            logger.info(
                f"🔄 [Update Current Week Pace] Found plan_id={plan.id}, "
                f"race_date={plan.race_date}"
            )

            # 2. Calculate current week number (week containing today)
            today = date.today()
            from src.utils.date_helpers import get_week_start_for_date

            # Get Monday of current week (not next Monday)
            current_week_monday = get_week_start_for_date(today)

            # Calculate weeks until race from current week's Monday
            days_until_race = (plan.race_date - current_week_monday).days

            # If race has already passed or is less than a week away, don't rebuild
            if days_until_race < 7:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "No current week to rebuild (race too soon or passed)",
                        }
                    ),
                    400,
                )

            # Calculate week number (weeks before race week)
            weeks_until_race = days_until_race // 7
            week_num = weeks_until_race if weeks_until_race > 0 else None

            if week_num is None:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "No current week to rebuild (race too soon or passed)",
                        }
                    ),
                    400,
                )

            logger.info(
                f"🔄 [Update Current Week Pace] Current week_num={week_num} (week starting {current_week_monday})"
            )

            # 3. Calculate new pace zones using runner-profile method
            logger.info(
                f"🔄 [Update Current Week Pace] Calculating new pace zones "
                f"(lookback_weeks={lookback_weeks})..."
            )
            new_pace_zones = get_runner_pace_zones_for_plan_generation(
                session=session,
                user_id=user_id,
                force_refresh=True,
                lookback_weeks=lookback_weeks,
            )

            logger.info(
                f"✅ [Update Current Week Pace] New pace zones calculated: "
                f"z2={new_pace_zones.pace_z2.low_sec:.1f}-{new_pace_zones.pace_z2.high_sec:.1f}s/mi, "
                f"m={new_pace_zones.marathon_sec:.1f}s/mi"
            )

            # 4. Fetch previous week logs (if available) for adjustments
            previous_week_logs = None
            if week_num > 1:
                try:
                    previous_week_logs = fetch_week_logs(
                        session=session,
                        plan_id=plan.id,
                        week_num=week_num - 1,
                        race_date=plan.race_date,
                    )
                    logger.info(
                        f"📊 [Update Current Week Pace] Fetched {len(previous_week_logs) if previous_week_logs else 0} "
                        f"previous week logs"
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️ [Update Current Week Pace] Could not fetch previous week logs: {e}"
                    )
                    previous_week_logs = None

            # 5. Rebuild week with new pace zones
            logger.info(
                f"🔄 [Update Current Week Pace] Rebuilding week {week_num} with new paces..."
            )

            rebuild_result = WeeklyRebuildService.rebuild_week(
                session=session,
                plan_id=plan.id,
                week_num=week_num,
                previous_week_logs=previous_week_logs,
                initial_pace_zones=new_pace_zones,
                skip_adaptive_adjustments=True,  # Force the new pace zones without adjustments
            )

            # 6. Commit changes
            session.commit()

            # 7. Verify pace_ranges were actually saved to database
            from src.db.models.plan_workouts import PlanWorkout
            from src.utils.date_helpers import get_week_start_for_date
            from datetime import timedelta

            # Calculate week dates from race date backwards (same logic as fetch_week_logs_from_db)
            weeks_before_race = week_num
            target_week_start = plan.race_date - timedelta(weeks=weeks_before_race)
            week_start = get_week_start_for_date(target_week_start)
            week_end = week_start + timedelta(days=6)

            # Get workouts for the week we just updated
            updated_workouts = (
                session.query(PlanWorkout)
                .filter(
                    PlanWorkout.plan_id == plan.id,
                    PlanWorkout.date >= week_start,
                    PlanWorkout.date <= week_end,
                )
                .order_by(PlanWorkout.date)
                .all()
            )

            pace_ranges_verified = sum(
                1 for w in updated_workouts if w.pace_ranges is not None
            )
            logger.info(
                f"✅ [Update Current Week Pace] Week {week_num} rebuilt successfully. "
                f"Verified: {pace_ranges_verified}/{len(updated_workouts)} workouts have pace_ranges in DB"
            )

            # Log the actual pace_ranges values from database
            for w in updated_workouts:
                if w.pace_ranges:
                    logger.info(
                        f"✅ [Update Current Week Pace] DB verification - Workout {w.id} ({w.date}): "
                        f"pace_ranges={w.pace_ranges}"
                    )

            # Format pace zones for response
            def sec_to_pace(sec):
                """Convert seconds per mile to mm:ss/mile format."""
                minutes = int(sec // 60)
                seconds = int(sec % 60)
                return f"{minutes}:{seconds:02d}/mi"

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": f"Week {week_num} rebuilt with new pace zones",
                        "plan_id": plan.id,
                        "week_num": week_num,
                        "lookback_weeks": lookback_weeks,
                        "pace_zones": {
                            "z2": {
                                "min": sec_to_pace(new_pace_zones.pace_z2.low_sec),
                                "max": sec_to_pace(new_pace_zones.pace_z2.high_sec),
                                "min_sec": round(new_pace_zones.pace_z2.low_sec, 1),
                                "max_sec": round(new_pace_zones.pace_z2.high_sec, 1),
                            },
                            "z3": {
                                "min": sec_to_pace(new_pace_zones.pace_z3.low_sec),
                                "max": sec_to_pace(new_pace_zones.pace_z3.high_sec),
                                "min_sec": round(new_pace_zones.pace_z3.low_sec, 1),
                                "max_sec": round(new_pace_zones.pace_z3.high_sec, 1),
                            },
                            "m": {
                                "pace": sec_to_pace(new_pace_zones.marathon_sec),
                                "sec": round(new_pace_zones.marathon_sec, 1),
                            },
                            "z4": {
                                "min": sec_to_pace(new_pace_zones.pace_z4.low_sec),
                                "max": sec_to_pace(new_pace_zones.pace_z4.high_sec),
                                "min_sec": round(new_pace_zones.pace_z4.low_sec, 1),
                                "max_sec": round(new_pace_zones.pace_z4.high_sec, 1),
                            },
                        },
                        "week1_long_cap": round(new_pace_zones.week1_long_cap, 1),
                        "rebuild_result": {
                            "updated_workouts": len(
                                rebuild_result.get("updated_workouts", [])
                            ),
                        },
                    }
                ),
                200,
            )

        except ValueError as e:
            logger.error(f"❌ [Update Current Week Pace] Validation error: {e}")
            session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception as e:
            logger.exception(f"❌ [Update Current Week Pace] Failed: {e}")
            session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
        finally:
            session.close()

    except Exception as e:
        logger.exception(f"❌ [Update Current Week Pace] Exception: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route("/backup-database", methods=["POST"])
@requires_auth
def backup_database():
    """
    Manually trigger a database backup.

    Creates a PostgreSQL backup and stores it in the configured backup location
    (Railway Volume at /backups or configured BACKUP_LOCAL_PATH).

    Returns:
        JSON response with backup status and file path
    """
    import os
    import subprocess
    from datetime import datetime
    from pathlib import Path

    logger.info("🔄 [Backup Database] Request received")

    try:
        # Get configuration
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return jsonify({"status": "error", "message": "DATABASE_URL not set"}), 500

        backup_path = os.getenv("BACKUP_LOCAL_PATH", "/backups")
        retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))

        # Ensure backup directory exists
        backup_dir = Path(backup_path)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"backup_{timestamp}.sql"

        logger.info(f"📦 [Backup Database] Creating backup: {backup_file}")

        # Run pg_dump
        result = subprocess.run(
            [
                "pg_dump",
                "--no-owner",
                "--no-acl",
                "--clean",
                "--if-exists",
                "-f",
                str(backup_file),
                db_url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Verify backup was created
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file was not created: {backup_file}")

        file_size = backup_file.stat().st_size
        if file_size == 0:
            raise ValueError(f"Backup file is empty: {backup_file}")

        logger.info(
            f"✅ [Backup Database] Backup created: {backup_file} ({file_size:,} bytes)"
        )

        # Cleanup old backups (optional, non-blocking)
        try:
            from datetime import timedelta

            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            deleted_count = 0

            for old_backup in backup_dir.glob("backup_*.sql"):
                if old_backup == backup_file:
                    continue  # Don't delete the backup we just created

                file_time = datetime.fromtimestamp(old_backup.stat().st_mtime)
                if file_time < cutoff_date:
                    old_backup.unlink()
                    deleted_count += 1
                    logger.info(
                        f"🗑️  [Backup Database] Deleted old backup: {old_backup.name}"
                    )

            if deleted_count > 0:
                logger.info(
                    f"✅ [Backup Database] Cleaned up {deleted_count} old backup(s)"
                )
        except Exception as cleanup_error:
            logger.warning(
                f"⚠️  [Backup Database] Cleanup failed (non-critical): {cleanup_error}"
            )

        # List current backups
        backups = sorted(backup_dir.glob("backup_*.sql"), reverse=True)
        backup_list = [
            {
                "filename": b.name,
                "size_bytes": b.stat().st_size,
                "created_at": datetime.fromtimestamp(b.stat().st_mtime).isoformat(),
            }
            for b in backups[:10]  # Last 10 backups
        ]

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Backup created successfully",
                    "backup_file": str(backup_file),
                    "size_bytes": file_size,
                    "backup_path": backup_path,
                    "recent_backups": backup_list,
                    "total_backups": len(backups),
                }
            ),
            200,
        )

    except subprocess.CalledProcessError as e:
        logger.exception(f"❌ [Backup Database] pg_dump failed: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Backup failed: {e.stderr}",
                }
            ),
            500,
        )
    except FileNotFoundError:
        logger.error("❌ [Backup Database] pg_dump not found")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "pg_dump not found. Install PostgreSQL client tools.",
                }
            ),
            500,
        )
    except Exception as e:
        logger.exception(f"❌ [Backup Database] Backup failed: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                }
            ),
            500,
        )
