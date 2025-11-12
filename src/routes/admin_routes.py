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
    Get list of all athletes for admin dropdown

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
import logging
from src.utils.auth0_jwt import requires_auth

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
def get_athletes():
    """Get list of all athletes for admin dropdown."""
    session = get_session()
    try:
        athletes = session.query(UserAthleteLink).all()
        athlete_list = [
            {
                "athlete_id": athlete.athlete_id,
                "user_id": str(athlete.user_id),
                "display_name": f"Athlete {athlete.athlete_id}",
            }
            for athlete in athletes
        ]
        return jsonify({"athletes": athlete_list}), 200
    except Exception as e:
        logger.exception(f"❌ Failed to fetch athletes")
        return jsonify({"status": "error", "message": str(e)}), 500
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
