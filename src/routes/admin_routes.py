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

admin_bp = Blueprint("admin", __name__)
logger = logging.getLogger(__name__)


@admin_bp.before_request
def log_admin_requests():
    """Log all requests to admin routes for debugging."""
    logger.info(f"[ADMIN] {request.method} {request.path}")


@admin_bp.route("/ping")
def ping():
    return "pong from admin"


@admin_bp.route("/test-no-auth", methods=["GET", "POST"])
def test_no_auth():
    """Test endpoint without auth to debug routing."""
    logger.info("✅ [TEST-NO-AUTH] This endpoint was hit!")
    return jsonify({"status": "success", "message": "Admin routes are working"}), 200


@admin_bp.route("/refresh-metrics", methods=["POST"])
@requires_auth
def refresh_metrics_wrapper():
    """Wrapper to debug requires_auth issues."""
    print("🔴 [WRAPPER] refresh_metrics endpoint reached!", flush=True)
    print(
        f"🔴 [WRAPPER] Authorization header: {bool(request.headers.get('Authorization'))}",
        flush=True,
    )

    # Manually trigger the metrics refresh
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
        logger.exception(f"❌ Exception during metrics refresh: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route("/trigger-ingest/<int:athlete_id>", methods=["POST"])
@requires_auth
def trigger_ingestion(athlete_id):
    logger.info(f"⏱️ [Trigger] Received trigger-ingest for athlete_id={athlete_id}")
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
            per_page=200,
        )

        if not result or result.get("fetched", 0) == 0:
            logger.info(f"📭 No activities fetched for athlete_id={athlete_id}")
        else:
            logger.info(f"✅ Ingestion completed: {result}")

        return jsonify({"status": "success", "result": result}), 200

    except Exception as e:
        logger.exception(f"❌ Exception during ingestion for athlete_id={athlete_id}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        session.close()


@admin_bp.route("/fetch-activity/<int:activity_id>", methods=["POST"])
@requires_auth
def fetch_single_activity(activity_id):
    """
    Manually fetch a single activity using webhook-style processing.

    This is perfect for pulling in activities that existed before
    the webhook was set up, or for manually syncing specific runs.

    Usage:
        POST /admin/fetch-activity/12345678

    Optional query params:
        - athlete_id: Specify athlete (otherwise auto-detect from user)
    """
    logger.info(f"🎯 [Manual Fetch] Fetching activity {activity_id}")
    session = get_session()

    try:
        # Get athlete_id from query params or auto-detect from current user
        athlete_id = request.args.get("athlete_id", type=int)

        if not athlete_id:
            # Try to get athlete_id from authenticated user
            from flask import g

            user_id = getattr(g, "user_id", None)
            if user_id:
                mapping = (
                    session.query(UserAthleteLink).filter_by(user_id=user_id).first()
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
                        "message": "athlete_id required (pass as query param or authenticate)",
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

        # Fetch activity from Strava (webhook-style!)
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

        # Prepare and store activity (same as webhook!)
        activity_data["activity_id"] = activity_data.pop("id", activity_id)
        activity_data["user_id"] = user_id

        inserted = ActivityDAO.upsert_activities(
            session, athlete_id, [activity_data], user_id=user_id
        )

        if inserted > 0:
            logger.info(f"✅ Successfully stored activity {activity_id}")
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": f"Activity {activity_id} fetched and stored",
                        "activity_id": activity_id,
                        "activity_type": activity_type,
                        "name": activity_data.get("name"),
                        "distance": activity_data.get("distance"),
                        "moving_time": activity_data.get("moving_time"),
                    }
                ),
                200,
            )
        else:
            logger.warning(f"⚠️ Activity {activity_id} not inserted (may already exist)")
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": f"Activity {activity_id} already exists",
                        "activity_id": activity_id,
                    }
                ),
                200,
            )

    except Exception as e:
        logger.exception(f"❌ Failed to fetch activity {activity_id}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        session.close()


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
def sync_activities():
    """Sync activities for a specific athlete in a date range."""
    try:
        data = request.get_json()
        athlete_id = data.get("athlete_id")
        start_date = data.get("start_date")  # YYYY-MM-DD format
        end_date = data.get("end_date")  # YYYY-MM-DD format

        if not athlete_id or not start_date or not end_date:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required fields: athlete_id, start_date, end_date",
                    }
                ),
                400,
            )

        # Convert dates to Unix timestamps
        from datetime import datetime

        start_timestamp = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        end_timestamp = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())

        logger.info(
            f"🔄 Syncing activities for athlete {athlete_id} from {start_date} to {end_date}"
        )

        # Call the existing function with date range
        result = run_full_ingestion_and_enrichment(
            _unused_session=None,
            athlete_id=athlete_id,
            after=start_timestamp,
            before=end_timestamp,
            max_activities=None,  # Use env var setting
        )

        return (
            jsonify(
                {
                    "status": "success",
                    "result": result,
                    "athlete_id": athlete_id,
                    "date_range": f"{start_date} to {end_date}",
                }
            ),
            200,
        )

    except Exception as e:
        logger.exception(f"❌ Failed to sync activities")
        return jsonify({"status": "error", "message": str(e)}), 500
