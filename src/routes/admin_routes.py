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

POST /admin/trigger-ingest/<athlete_id>
    Manually trigger activity ingestion for an athlete

POST /admin/fetch-activity/<activity_id>
    Manually fetch a single activity from Strava

GET  /admin/athletes
    Get list of all athletes for admin dropdown (requires auth)

POST /admin/delete-user
    Permanently delete a user account by internal user_id (admin only; ADMIN_USER_IDS)

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

    Requires ADMIN_USER_IDS to include the caller's internal g.user_id.
    Body: {"user_id": "<uuid>", "confirm": true}
    """
    from flask import g

    if not is_admin():
        return (
            jsonify(
                {
                    "error": "Admin access required",
                    "hint": "Set ADMIN_USER_IDS to a comma-separated list of internal user UUIDs.",
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

                enrich_one_activity_with_refresh(
                    session, athlete_id, activity_id, fetch_streams=True
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

        # Get user_id for this athlete if not already set
        if not user_id:
            mapping = (
                session.query(UserAthleteLink).filter_by(athlete_id=athlete_id).first()
            )
            if mapping:
                user_id = mapping.user_id
                logger.info(
                    f"✅ [Sync Activities] Found user_id={user_id} for athlete_id={athlete_id}"
                )

        # Log if syncing for different athlete (audit trail for admin operations)
        if user_id:
            mapping = (
                session.query(UserAthleteLink)
                .filter_by(user_id=user_id, athlete_id=athlete_id)
                .first()
            )
            if not mapping:
                logger.info(
                    f"🔄 [Sync Activities] Admin sync: User {user_id} syncing athlete {athlete_id} "
                    f"(not their own athlete - admin operation)"
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
                    if result.get("enriched", 0) == 0:
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
                sync_job, athlete_id, user_id, start_timestamp, end_timestamp
            )
            logger.info(
                f"✅ [Sync Activities] Background job launched, returning 202 response"
            )

            # Return immediately - sync is running in background
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": f"Sync started for athlete {athlete_id} from {start_date} to {end_date}. Processing in background...",
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
        logger.exception(f"❌ [Sync Activities] Failed to sync activities: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        session.close()


@admin_bp.route("/migrate-prod-to-local", methods=["POST"])
@requires_auth
def migrate_prod_to_local():
    """
    Trigger migration from production database to local database.

    This endpoint copies data from production (main Strava account) to local
    (test Strava account) and updates all IDs to work with the local environment.

    The migration copies:
    - user_identity, user_athletes, user_profile
    - activities, splits
    - plans, plan_workouts, weekly_metrics, weekly_decision_log
    - strava_sync_status, conversations

    Request body (optional):
        - full (boolean): If true, force full migration (ignore last migration timestamp)
                          If false or omitted, uses incremental/delta migration

    Returns:
        JSON response with migration status and summary
    """
    logger.info("🔄 [Migration] Production to local migration requested")

    try:
        data = request.get_json() or {}
        full_migration = data.get("full", False)

        if full_migration:
            logger.info("🔄 [Migration] Full migration mode (all data)")
        else:
            logger.info("🔄 [Migration] Incremental migration mode (delta only)")

        # Import required modules
        import os
        import sys
        from pathlib import Path
        from dotenv import load_dotenv

        # Load environment variables
        env_local = Path(".env.local")
        env_prod = Path(".env.prod")

        if env_local.exists():
            load_dotenv(env_local, override=False)

        if env_prod.exists():
            load_dotenv(env_prod, override=False)

        # Get database URLs
        prod_db_url = os.getenv("PROD_DATABASE_URL") or os.getenv("DATABASE_URL")
        local_db_url = os.getenv("DATABASE_URL")

        if not prod_db_url:
            return (
                jsonify(
                    {"status": "error", "message": "PROD_DATABASE_URL not configured"}
                ),
                400,
            )

        if not local_db_url:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "DATABASE_URL (local) not configured",
                    }
                ),
                400,
            )

        # Import DataMigrator class (dynamically to avoid import issues at module load)
        try:
            # Add scripts to path if needed
            scripts_path = str(
                Path(__file__).resolve().parent.parent.parent / "scripts"
            )
            if scripts_path not in sys.path:
                sys.path.insert(0, scripts_path)

            from migrate_prod_to_local import DataMigrator
        except ImportError as e:
            logger.error(f"❌ [Migration] Could not import DataMigrator: {e}")
            import traceback

            traceback.print_exc()
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Could not import migration script: {str(e)}",
                    }
                ),
                500,
            )

        # Run migration using the script's run_migration method
        try:
            with DataMigrator(
                prod_db_url, local_db_url, force=full_migration
            ) as migrator:
                # Run complete migration process
                migrator.run_migration()

            logger.info("✅ [Migration] Migration completed successfully")
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Migration completed successfully. Data copied from production to local database.",
                        "mode": "full" if full_migration else "incremental",
                    }
                ),
                200,
            )

        except Exception as e:
            logger.exception(f"❌ [Migration] Error during migration: {e}")
            import traceback

            traceback.print_exc()
            return (
                jsonify({"status": "error", "message": f"Migration failed: {str(e)}"}),
                500,
            )

    except Exception as e:
        logger.exception(f"❌ [Migration] Exception during migration: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


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
        from src.services.training_plan.pace import get_initial_pace_seed

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
        week1_long = data.get("week1_long", 8.0)
        lookback_weeks = data.get("lookback_weeks", 6)

        logger.info(
            f"🧪 [Test Pace Calculation] Calculating for user_id={user_id}, "
            f"week1_long={week1_long}, lookback_weeks={lookback_weeks}"
        )

        session = get_session()
        try:
            # Calculate pace seed
            seed = get_initial_pace_seed(
                session=session,
                user_id=user_id,
                week1_long=week1_long,
                lookback_weeks=lookback_weeks,
            )

            # Check calculation method used
            from src.db.models.activities import Activity
            from sqlalchemy import text
            from datetime import datetime, timedelta

            cutoff = datetime.now() - timedelta(weeks=6)
            # Check if we have enough runs for performance-based calculation
            count_query = text(
                """
                SELECT COUNT(*) as run_count
                FROM activities
                WHERE user_id = :user_id
                  AND type = 'Run'
                  AND start_date >= :cutoff
                  AND conv_distance >= 2.0
                  AND moving_time IS NOT NULL
                  AND moving_time > 0
                  AND conv_distance > 0
                  AND (moving_time::float / conv_distance) BETWEEN 360 AND 1200
            """
            )

            run_count = session.execute(
                count_query, {"user_id": user_id, "cutoff": cutoff}
            ).scalar()

            calculation_method = (
                "Performance-Based" if run_count >= 6 else "Calibration"
            )

            # Format pace zones for display
            def sec_to_pace(sec):
                """Convert seconds per mile to mm:ss/mile format."""
                minutes = int(sec // 60)
                seconds = int(sec % 60)
                return f"{minutes}:{seconds:02d}/mi"

            result = {
                "status": "success",
                "user_id": user_id,
                "calculation_method": calculation_method,
                "runs_used": run_count if run_count >= 6 else 0,
                "lookback_weeks": lookback_weeks,
                "pace_zones": {
                    "Easy": {
                        "min": sec_to_pace(seed.E_min),
                        "max": sec_to_pace(seed.E_max),
                        "min_sec": round(seed.E_min, 1),
                        "max_sec": round(seed.E_max, 1),
                    },
                    "Steady": {
                        "min": sec_to_pace(seed.S_min),
                        "max": sec_to_pace(seed.S_max),
                        "min_sec": round(seed.S_min, 1),
                        "max_sec": round(seed.S_max, 1),
                    },
                    "Marathon": {
                        "pace": sec_to_pace(seed.M),
                        "sec": round(seed.M, 1),
                    },
                    "Threshold": {
                        "min": sec_to_pace(seed.T_min),
                        "max": sec_to_pace(seed.T_max),
                        "min_sec": round(seed.T_min, 1),
                        "max_sec": round(seed.T_max, 1),
                    },
                },
                "week1_long_cap": round(seed.week1_long_cap, 1),
            }

            logger.info(
                f"✅ [Test Pace Calculation] Success: method={calculation_method}, "
                f"marathon_pace={sec_to_pace(seed.M)}"
            )

            return jsonify(result), 200

        finally:
            session.close()

    except Exception as e:
        logger.exception(f"❌ [Test Pace Calculation] Failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route("/test-median-easy-pace-debug", methods=["POST"])
@requires_auth
def test_median_easy_pace_debug():
    """
    Debug endpoint - shows all data used in median easy pace calculation.

    This endpoint helps verify the SQL calculation is correct by showing:
    - All runs used in the calculation
    - SQL median vs manual Python median (for comparison)
    - Min, max, avg paces
    - Individual run details

    Request body (JSON):
        - user_id (str, optional): User UUID to test. If not provided, uses authenticated user.
        - lookback_weeks (int, optional): Weeks of history to analyze (default: 6)

    Returns:
        JSON response with detailed calculation data for verification.
    """
    logger.info("🧪 [Test Median Easy Pace Debug] Request received")

    try:
        from flask import g
        from sqlalchemy import text
        from datetime import datetime, timedelta

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
            f"🧪 [Test Median Easy Pace Debug] Calculating for user_id={user_id}, "
            f"lookback_weeks={lookback_weeks}"
        )

        session = get_session()
        try:
            cutoff = datetime.now() - timedelta(weeks=lookback_weeks)

            # Get all valid runs with their paces
            query = text(
                """
                SELECT
                    activity_id,
                    start_date,
                    conv_distance,
                    moving_time,
                    moving_time::float / conv_distance AS pace_sec_per_mile
                FROM activities
                WHERE user_id = :user_id
                  AND type = 'Run'
                  AND start_date >= :cutoff
                  AND conv_distance >= 2.0
                  AND moving_time IS NOT NULL
                  AND moving_time > 0
                  AND conv_distance > 0
                  AND (moving_time::float / conv_distance) BETWEEN 360 AND 1200
                ORDER BY pace_sec_per_mile
            """
            )

            results = session.execute(
                query, {"user_id": user_id, "cutoff": cutoff}
            ).fetchall()

            if len(results) < 6:
                return jsonify(
                    {
                        "status": "insufficient_data",
                        "run_count": len(results),
                        "message": "Need at least 6 runs (2+ miles) in last 6 weeks",
                        "cutoff_date": cutoff.isoformat(),
                    }
                )

            # Calculate median manually for comparison
            paces = [float(r.pace_sec_per_mile) for r in results]
            sorted_paces = sorted(paces)
            median_index = len(sorted_paces) // 2
            if len(sorted_paces) % 2 == 1:
                manual_median = sorted_paces[median_index]
            else:
                manual_median = (
                    sorted_paces[median_index - 1] + sorted_paces[median_index]
                ) / 2

            # SQL median
            median_query = text(
                """
                WITH valid_runs AS (
                    SELECT moving_time::float / conv_distance AS pace_sec_per_mile
                    FROM activities
                    WHERE user_id = :user_id
                      AND type = 'Run'
                      AND start_date >= :cutoff
                      AND conv_distance >= 2.0
                      AND moving_time IS NOT NULL
                      AND moving_time > 0
                      AND conv_distance > 0
                      AND (moving_time::float / conv_distance) BETWEEN 360 AND 1200
                )
                SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_sec_per_mile) AS median_pace
                FROM valid_runs
            """
            )

            sql_median = session.execute(
                median_query, {"user_id": user_id, "cutoff": cutoff}
            ).scalar()

            # Format pace for display
            def sec_to_pace(sec):
                """Convert seconds per mile to mm:ss/mile format."""
                minutes = int(sec // 60)
                seconds = int(sec % 60)
                return f"{minutes}:{seconds:02d}/mi"

            return jsonify(
                {
                    "status": "success",
                    "user_id": user_id,
                    "lookback_weeks": lookback_weeks,
                    "cutoff_date": cutoff.isoformat(),
                    "run_count": len(results),
                    "sql_median_sec": (
                        round(float(sql_median), 1) if sql_median else None
                    ),
                    "sql_median_formatted": (
                        sec_to_pace(sql_median) if sql_median else None
                    ),
                    "manual_median_sec": round(manual_median, 1),
                    "manual_median_formatted": sec_to_pace(manual_median),
                    "min_pace_sec": round(float(min(paces)), 1),
                    "min_pace_formatted": sec_to_pace(min(paces)),
                    "max_pace_sec": round(float(max(paces)), 1),
                    "max_pace_formatted": sec_to_pace(max(paces)),
                    "avg_pace_sec": round(float(sum(paces) / len(paces)), 1),
                    "avg_pace_formatted": sec_to_pace(sum(paces) / len(paces)),
                    "match": (
                        abs(float(sql_median) - manual_median) < 0.1
                        if sql_median
                        else False
                    ),
                    "difference_sec": (
                        round(abs(float(sql_median) - manual_median), 2)
                        if sql_median
                        else None
                    ),
                    "all_paces_sec": [round(p, 1) for p in sorted_paces],
                    "runs": [
                        {
                            "activity_id": r.activity_id,
                            "date": r.start_date.isoformat() if r.start_date else None,
                            "distance_mi": round(float(r.conv_distance), 2),
                            "moving_time_sec": r.moving_time,
                            "pace_sec_per_mile": round(float(r.pace_sec_per_mile), 1),
                            "pace_formatted": sec_to_pace(r.pace_sec_per_mile),
                        }
                        for r in results
                    ],
                }
            )
        finally:
            session.close()

    except Exception as e:
        logger.exception(f"❌ [Test Median Easy Pace Debug] Exception: {e}")
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
        from src.services.training_plan.pace import get_initial_pace_seed
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

            # 3. Calculate new pace seed using performance-based method
            logger.info(
                f"🔄 [Update Current Week Pace] Calculating new pace zones "
                f"(lookback_weeks={lookback_weeks})..."
            )

            # Get week1_long from plan if available, otherwise default
            week1_long = 8.0
            if plan.workouts:
                # Find first week's long run
                first_week_workouts = sorted(plan.workouts, key=lambda w: w.date)[:7]
                long_runs = [
                    w.miles
                    for w in first_week_workouts
                    if w.workout_type in ("Long Run", "long") and w.miles
                ]
                if long_runs:
                    week1_long = max(long_runs)

            new_pace_seed = get_initial_pace_seed(
                session=session,
                user_id=user_id,
                week1_long=week1_long,
                lookback_weeks=lookback_weeks,
            )

            logger.info(
                f"✅ [Update Current Week Pace] New pace zones calculated: "
                f"Easy={new_pace_seed.E_min:.1f}-{new_pace_seed.E_max:.1f}s/mi, "
                f"Marathon={new_pace_seed.M:.1f}s/mi"
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

            # 5. Rebuild week with new pace seed
            logger.info(
                f"🔄 [Update Current Week Pace] Rebuilding week {week_num} with new paces..."
            )

            rebuild_result = WeeklyRebuildService.rebuild_week(
                session=session,
                plan_id=plan.id,
                week_num=week_num,
                previous_week_logs=previous_week_logs,
                initial_seed=new_pace_seed,
                skip_adaptive_adjustments=True,  # Force the new pace seed without adjustments
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
                            "Easy": {
                                "min": sec_to_pace(new_pace_seed.E_min),
                                "max": sec_to_pace(new_pace_seed.E_max),
                                "min_sec": round(new_pace_seed.E_min, 1),
                                "max_sec": round(new_pace_seed.E_max, 1),
                            },
                            "Steady": {
                                "min": sec_to_pace(new_pace_seed.S_min),
                                "max": sec_to_pace(new_pace_seed.S_max),
                                "min_sec": round(new_pace_seed.S_min, 1),
                                "max_sec": round(new_pace_seed.S_max, 1),
                            },
                            "Marathon": {
                                "pace": sec_to_pace(new_pace_seed.M),
                                "sec": round(new_pace_seed.M, 1),
                            },
                            "Threshold": {
                                "min": sec_to_pace(new_pace_seed.T_min),
                                "max": sec_to_pace(new_pace_seed.T_max),
                                "min_sec": round(new_pace_seed.T_min, 1),
                                "max_sec": round(new_pace_seed.T_max, 1),
                            },
                        },
                        "week1_long_cap": round(new_pace_seed.week1_long_cap, 1),
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
