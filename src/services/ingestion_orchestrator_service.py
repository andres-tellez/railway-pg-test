"""
Strava Activity Ingestion Orchestrator
=======================================

This module orchestrates the full ingestion and enrichment process for Strava activities.

The ingestion process includes:
1. Token validation and retrieval
2. Sync strategy determination (full vs. incremental)
3. Activity fetching from Strava API
4. Activity filtering (runs only)
5. Activity storage in database
6. Activity enrichment (streams, splits, metrics)

Key Features:
- Incremental Sync: Only fetches new activities since last sync (efficient)
- Full Sync: Fetches all activities when needed (first sync, force flag)
- Automatic Enrichment: Automatically enriches activities with streams and metrics
- Error Handling: Comprehensive error handling with logging
- Input Validation: Validates all parameters before processing

Sync Strategies:
- Incremental: Fetches activities since last sync timestamp (default)
- Full: Fetches all activities within lookback period (first sync or force flag)

Processing Flow:
1. Validate athlete_id and parameters
2. Get valid access token (auto-refresh if expired)
3. Determine sync strategy (incremental vs. full)
4. Fetch activities from Strava API
5. Filter for runs only
6. Store new activities in database
7. Trigger enrichment batch for new activities
8. Update last sync timestamp

Usage:
    from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment

    result = run_full_ingestion_and_enrichment(
        _unused_session=None,
        athlete_id=12345,
        user_id="user-uuid",
        lookback_days=365,
        max_activities=1000,
        force_full_sync=False
    )
    # Returns: {"synced": 50, "enriched": 50}

Parameters:
- athlete_id: Strava athlete ID (required)
- user_id: Internal user ID (optional, UUID format)
- lookback_days: Number of days to look back (default: 365, max: 3650)
- max_activities: Maximum activities to fetch (default: from config)
- batch_size: Batch size for enrichment (optional)
- per_page: Activities per API page (optional, max: 200)
- after: Unix timestamp - only fetch activities after this time (optional)
- before: Unix timestamp - only fetch activities before this time (optional)
- force_full_sync: Force full sync instead of incremental (default: False)

Returns:
    Dict with "synced" and "enriched" counts:
    {
        "synced": 50,      # Number of activities synced from Strava
        "enriched": 50     # Number of activities enriched with streams/metrics
    }

Error Handling:
- Invalid athlete_id: Raises ValueError
- Invalid parameters: Logs warning and uses defaults
- API errors: Logged and propagated
- Database errors: Logged and propagated

References:
- https://developers.strava.com/docs/reference/#api-Activities
- https://developers.strava.com/docs/reference/#api-Streams
"""

import os
import time
import logging
from datetime import datetime, timedelta

from src.db.db_session import get_session
from src.db.dao.token_dao import get_tokens_sa
from src.db.dao.activity_dao import ActivityDAO
from src.db.models.tokens import Token
from src.db.models.activities import Activity
from src.services.token_service import get_valid_token
from src.services.activity_service import (
    ActivityIngestionService,
    run_enrichment_batch,
)
from src.services.sync_tracking_service import (
    should_use_incremental_sync,
    update_last_sync_timestamp,
)
from src.utils.seeder import seed_sample_activity
from src.utils.config import config
from src.utils.strava_exceptions import (
    StravaIngestionValidationError,
    StravaIngestionSyncError,
    StravaIngestionEnrichmentError,
    StravaTokenError,
)
from src.db.dao.strava_sync_status_dao import StravaSyncStatusDAO

logger = logging.getLogger(__name__)


def run_full_ingestion_and_enrichment(
    _unused_session,
    athlete_id,
    user_id=None,
    lookback_days=config.DEFAULT_LOOKBACK_DAYS,
    max_activities=config.MAX_ACTIVITIES_TO_DOWNLOAD,
    batch_size=None,
    per_page=None,
    after=None,
    before=None,
    force_full_sync=False,
):
    """
    Run full ingestion and enrichment for an athlete.

    Args:
        _unused_session: Unused session parameter (for backward compatibility)
        athlete_id: Strava athlete ID (required, must be positive integer)
        user_id: Internal user ID (optional, UUID format)
        lookback_days: Number of days to look back (default: 365, max: 3650)
        max_activities: Maximum activities to fetch (default: from config)
        batch_size: Batch size for enrichment (optional)
        per_page: Activities per API page (optional, max: 200)
        after: Unix timestamp - only fetch activities after this time (optional)
        before: Unix timestamp - only fetch activities before this time (optional)
        force_full_sync: Force full sync instead of incremental (default: False)

    Returns:
        Dict with "synced" and "enriched" counts

    Raises:
        ValueError: If athlete_id is invalid
    """
    from src.utils.strava_validators import (
        validate_athlete_id,
        validate_ingestion_params,
    )

    # Validate athlete_id
    validated_athlete_id, error = validate_athlete_id(athlete_id)
    if error:
        logger.error(f"Invalid athlete_id: {athlete_id}")
        raise StravaIngestionValidationError(
            message=f"Invalid athlete_id: {error[0].json.get('error', 'Unknown error')}",
            validation_errors={
                "athlete_id": error[0].json.get("error", "Invalid format")
            },
        )
    athlete_id = validated_athlete_id

    # Validate user_id if provided
    if user_id is not None:
        from src.utils.strava_validators import validate_user_id

        validated_user_id, error = validate_user_id(user_id)
        if error:
            logger.warning(
                f"Invalid user_id format: {user_id}, continuing without user_id"
            )
            user_id = None  # Continue without user_id rather than failing

    # Validate ingestion parameters
    params, error = validate_ingestion_params(
        lookback_days=lookback_days,
        max_activities=max_activities,
        batch_size=batch_size,
        per_page=per_page,
    )
    if error:
        logger.warning(
            f"Invalid ingestion parameters, using defaults: {error[0].json.get('error')}"
        )
        # Use defaults instead of failing - keep original values or use defaults
        if (
            lookback_days is None
            or not isinstance(lookback_days, int)
            or lookback_days < 1
        ):
            lookback_days = config.DEFAULT_LOOKBACK_DAYS
        if (
            max_activities is None
            or not isinstance(max_activities, int)
            or max_activities < 1
        ):
            max_activities = config.MAX_ACTIVITIES_TO_DOWNLOAD
        # batch_size and per_page can remain None if invalid
    else:
        # Use validated parameters
        if params:
            if "lookback_days" in params:
                lookback_days = params["lookback_days"]
            if "max_activities" in params:
                max_activities = params["max_activities"]
            if "batch_size" in params:
                batch_size = params["batch_size"]
            if "per_page" in params:
                per_page = params["per_page"]

    session = get_session()
    sync_status_dao = StravaSyncStatusDAO(session) if user_id else None

    def sync_start():
        if not sync_status_dao:
            return
        try:
            sync_status_dao.start_sync(user_id, athlete_id)
        except Exception as exc:  # pragma: no cover - best-effort logging
            logger.warning(f"Failed to start sync status tracking: {exc}")

    def sync_progress(progress: float, step: str, detail: str | None = None):
        if not sync_status_dao:
            return
        try:
            sync_status_dao.update_progress(
                user_id, athlete_id, progress=progress, step=step, detail=detail
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Failed to update sync progress: {exc}")

    def sync_complete(message: str = "Sync complete"):
        if not sync_status_dao:
            return
        try:
            sync_status_dao.update_progress(
                user_id, athlete_id, progress=100.0, step=message
            )
            sync_status_dao.mark_complete(user_id, athlete_id)
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Failed to mark sync complete: {exc}")

    def sync_error(detail: str, error_code: str | None = None):
        if not sync_status_dao:
            return
        try:
            sync_status_dao.mark_error(
                user_id, athlete_id, detail=detail, error_code=error_code
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Failed to record sync error: {exc}")

    logger.info(
        f"[Ingestion] run_full_ingestion_and_enrichment called for user_id={user_id}, athlete_id={athlete_id}"
    )

    try:
        logger.info(
            f"[CRON SYNC] Sync job started at {datetime.utcnow().isoformat()} "
            f"for user_id={user_id}, athlete_id={athlete_id}"
        )
        sync_start()
        sync_progress(5, "Preparing sync")

        max_activities = max_activities or config.MAX_ACTIVITIES_TO_DOWNLOAD
        batch_size = batch_size or config.DEFAULT_BATCH_SIZE
        per_page = per_page or config.DEFAULT_PER_PAGE

        # Token handling
        tokens = get_tokens_sa(session, athlete_id)
        if not tokens:
            access_token = os.getenv("STRAVA_ACCESS_TOKEN")
            refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
            expires_at = int(os.getenv("STRAVA_EXPIRES_AT", time.time() + 3600))
            if access_token and refresh_token:
                token = Token(
                    athlete_id=athlete_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                )
                session.merge(token)
                session.commit()
                logger.info("Seeded fallback Strava token")
            else:
                seed_sample_activity(session, athlete_id)
                session.commit()
                logger.info("Mock activity seeded")
                sync_complete("Seeded sample activity")
                return {"synced": 1, "enriched": 0}

        access_token = get_valid_token(session, athlete_id)
        logger.info("Access granted")
        sync_progress(10, "Access token validated")

        # Webhooks-first strategy: Use incremental sync if webhooks are active
        use_incremental, last_sync_at = should_use_incremental_sync(
            session, athlete_id, force_full=force_full_sync
        )

        if use_incremental and last_sync_at:
            # Incremental sync: Only fetch activities after last sync
            after = after or int(last_sync_at.timestamp())
            logger.info(
                f"🔄 Incremental sync: fetching activities after {last_sync_at.isoformat()}"
            )
        else:
            # Full sync: Use lookback_days or provided 'after'
            after = after or int(
                (datetime.utcnow() - timedelta(days=lookback_days))
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .timestamp()
            )
            logger.info(
                f"🔄 Full sync: fetching activities from {lookback_days} days ago"
            )

        before = before or int(
            datetime.utcnow()
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        logger.info("Prepared date window")
        sync_progress(20, "Fetching activities from Strava…")

        service = ActivityIngestionService(session, athlete_id)
        logger.info("Fetching recent runs from Strava...")

        try:
            all_fetched = service.client.get_activities(
                after=after, before=before, per_page=per_page, limit=max_activities
            )
        except StravaTokenError as e:
            logger.error(f"Token error during activity fetch: {e}", exc_info=True)
            raise StravaIngestionSyncError(
                athlete_id=athlete_id,
                reason=f"Token error: {e.message}",
                message="Failed to fetch activities due to token error",
            )
        except Exception as e:
            logger.error(f"Failed to fetch activities: {e}", exc_info=True)
            raise StravaIngestionSyncError(
                athlete_id=athlete_id,
                reason=str(e),
                message="Failed to fetch activities from Strava API",
            )

        logger.info(f"Fetched {len(all_fetched)} activities")

        runs_only = [a for a in all_fetched if a.get("type") == "Run"]
        logger.info(f"Identified {len(runs_only)} runs")
        sync_progress(
            35,
            "Processing activities",
            detail=f"Fetched {len(runs_only)} runs",
        )

        if not runs_only:
            logger.info("No runs found in Strava account")
            sync_complete("No new runs found")
            return {"synced": 0, "enriched": 0}

        fetched_ids = [int(a.get("id")) for a in runs_only if a.get("id")]
        existing_ids = {
            r[0]
            for r in session.query(Activity.activity_id)
            .filter(Activity.activity_id.in_(fetched_ids))
            .all()
        }

        new_activities = [a for a in runs_only if int(a.get("id")) not in existing_ids]
        for a in new_activities:
            a["activity_id"] = a.pop("id", None)
            a["user_id"] = user_id  # store user_id (UUID) alongside activity

        # Deduplicate by activity_id
        dedup = {
            int(a["activity_id"]): a for a in new_activities if a.get("activity_id")
        }
        unique_new_activities = list(dedup.values())

        logger.info(f"Saving {len(unique_new_activities)} new runs...")

        inserted_count = ActivityDAO.upsert_activities(
            session, athlete_id, unique_new_activities, user_id=user_id
        )

        logger.info(f"Synced {inserted_count} new runs")
        sync_progress(
            60,
            "Saving activities",
            detail=f"Saved {inserted_count} new runs",
        )

        logger.info("Enriching activities...")

        try:
            enriched = (
                run_enrichment_batch(session, athlete_id, batch_size=batch_size) or 0
            )
            logger.info(f"Enriched {enriched} activities")
        except StravaTokenError as e:
            logger.error(f"Token error during enrichment: {e}", exc_info=True)
            # Don't fail ingestion if enrichment fails - log and continue
            enriched = 0
            logger.warning(
                f"Enrichment skipped due to token error, but ingestion completed"
            )
        except Exception as e:
            logger.error(f"Enrichment failed: {e}", exc_info=True)
            # Don't fail ingestion if enrichment fails - log and continue
            enriched = 0
            logger.warning(f"Enrichment failed, but ingestion completed")

        sync_progress(
            80,
            "Enrichment complete",
            detail=f"Enriched {enriched} activities",
        )

        # Refresh materialized views after successful ingestion
        try:
            from sqlalchemy import text

            session.execute(text("REFRESH MATERIALIZED VIEW mv_athlete_metrics;"))
            session.execute(text("REFRESH MATERIALIZED VIEW mv_longest_runs;"))
            session.commit()
            logger.info("✅ Refreshed materialized views for metrics and longest runs")
            sync_progress(90, "Refreshing metrics")
        except Exception as e:
            logger.error(f"❌ Failed to refresh materialized view: {e}")
            import traceback

            logger.error(traceback.format_exc())

        # Invalidate metrics cache for this athlete after successful ingestion
        try:
            from src.services.metrics_cache_service import invalidate_athlete_cache

            invalidate_athlete_cache(athlete_id)
            logger.info(f"Invalidated metrics cache for athlete {athlete_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for athlete {athlete_id}: {e}")

        # Update last sync timestamp (tracked via most recent activity)
        update_last_sync_timestamp(session, athlete_id)
        sync_progress(95, "Finalizing sync")
        logger.info(f"Finished ingestion. Synced={inserted_count}, Enriched={enriched}")
        sync_complete()
        return {"synced": inserted_count, "enriched": enriched}

    except (
        StravaIngestionValidationError,
        StravaIngestionSyncError,
        StravaIngestionEnrichmentError,
    ) as e:
        # Re-raise our custom exceptions as-is
        session.rollback()
        sync_error(f"Sync failed: {e}", error_code=e.__class__.__name__)
        raise
    except StravaTokenError as e:
        session.rollback()
        logger.exception(f"Token error during ingestion: {e}")
        sync_error(f"Token error during sync: {e.message}", error_code="TOKEN_ERROR")
        raise StravaIngestionSyncError(
            athlete_id=athlete_id if "athlete_id" in locals() else None,
            reason=f"Token error: {e.message}",
            message="Ingestion failed due to token error",
        )
    except Exception as e:
        session.rollback()
        logger.exception(f"Ingestion failed: {e}")
        sync_error(f"Ingestion failed: {e}", error_code="INGESTION_ERROR")
        raise StravaIngestionSyncError(
            athlete_id=athlete_id if "athlete_id" in locals() else None,
            reason=str(e),
            message="Ingestion failed with unexpected error",
        )
    finally:
        session.close()
