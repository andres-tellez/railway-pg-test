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
from datetime import datetime, timedelta, timezone, time as dt_time

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
from src.utils.date_helpers import get_current_week_start
from src.utils.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


def run_full_ingestion_and_enrichment(
    _unused_session,
    athlete_id,
    user_id=None,
    lookback_days=config.DEFAULT_LOOKBACK_DAYS,
    max_activities=None,
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
        # batch_size and per_page can remain None if invalid
    else:
        # Use validated parameters
        if params:
            if "lookback_days" in params:
                lookback_days = params["lookback_days"]
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

        current_week_start = get_current_week_start()
        six_week_start = current_week_start - timedelta(weeks=6)
        two_week_cutoff = current_week_start - timedelta(weeks=2)

        six_week_start_dt = datetime.combine(
            six_week_start, dt_time.min, tzinfo=timezone.utc
        )
        two_week_cutoff_dt = datetime.combine(
            two_week_cutoff, dt_time.min, tzinfo=timezone.utc
        )

        window_after_ts = int(six_week_start_dt.timestamp())
        now_ts = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())

        current_week_start = get_current_week_start()
        six_week_start = current_week_start - timedelta(weeks=6)
        two_week_cutoff = current_week_start - timedelta(weeks=2)

        six_week_start_dt = datetime.combine(
            six_week_start, dt_time.min, tzinfo=timezone.utc
        )
        two_week_cutoff_dt = datetime.combine(
            two_week_cutoff, dt_time.min, tzinfo=timezone.utc
        )

        window_after_ts = int(six_week_start_dt.timestamp())
        now_ts = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())

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

        after_ts = max(window_after_ts, after or 0)
        before_ts = before or now_ts

        if use_incremental and last_sync_at:
            # Incremental sync: Only fetch activities after last sync
            last_sync_ts = int(last_sync_at.timestamp())
            after_ts = max(after_ts, last_sync_ts)
            logger.info(
                f"🔄 Incremental sync: fetching activities after {datetime.fromtimestamp(after_ts, tz=timezone.utc).isoformat()}"
            )
        else:
            logger.info(
                f"🔄 Full sync: fetching activities from {six_week_start_dt.isoformat()} (last 6 full weeks + current week)"
            )

        logger.info(
            "Prepared date window: after=%s, before=%s",
            datetime.fromtimestamp(after_ts, tz=timezone.utc).isoformat(),
            datetime.fromtimestamp(before_ts, tz=timezone.utc).isoformat(),
        )
        sync_progress(20, "Fetching activities from Strava…")

        service = ActivityIngestionService(session, athlete_id)
        logger.info("Fetching recent runs from Strava...")

        try:
            all_fetched = service.fetch_all_activities(
                after=after_ts,
                before=before_ts,
                per_page=per_page,
                type_filter="Run",
                type_limit=None,
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

        logger.info(f"Fetched {len(all_fetched)} run activities")
        runs_only = []
        for activity in all_fetched:
            start_date_str = activity.get("start_date")
            if not start_date_str:
                runs_only.append(activity)
                continue
            try:
                start_dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            except ValueError:
                runs_only.append(activity)
                continue
            if start_dt >= six_week_start_dt:
                runs_only.append(activity)
        projected_enrichment_calls = 0
        for act in runs_only:
            start_date_str = act.get("start_date")
            try:
                start_dt = (
                    datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                    if start_date_str
                    else None
                )
            except Exception:
                start_dt = None
            projected_enrichment_calls += 2  # detail + zones
            if start_dt and start_dt >= two_week_cutoff_dt:
                projected_enrichment_calls += 1  # streams/splits

        rate_limiter = get_rate_limiter()
        stats = rate_limiter.get_stats()
        remaining_15m = stats.get("remaining_15min", 0)
        logger.info(
            "Projected Strava calls: detail/zones/streams=%d, remaining window=%d",
            projected_enrichment_calls,
            remaining_15m,
        )

        RATE_BUFFER = 10
        if projected_enrichment_calls + RATE_BUFFER > remaining_15m:
            wait_seconds = max(stats.get("wait_time_seconds", 0), 60)
            message = (
                "Strava is handling a lot of requests right now. "
                f"Please wait about {int(wait_seconds // 60) + 1} minutes before trying again."
            )
            logger.warning(
                "Rate limit headroom too low (%d remaining, %d needed). Aborting sync.",
                remaining_15m,
                projected_enrichment_calls + RATE_BUFFER,
            )
            sync_error(message, error_code="RATE_LIMIT_WINDOW")
            raise StravaIngestionSyncError(
                athlete_id=athlete_id,
                reason="rate_limit_headroom_exceeded",
                message=message,
            )

        sync_progress(
            35,
            "Processing activities",
            detail=f"Fetched {len(runs_only)} runs",
        )

        inserted_count = 0
        if runs_only:
            fetched_ids = [
                int(a.get("id") or a.get("activity_id"))
                for a in runs_only
                if a.get("id") or a.get("activity_id")
            ]
            existing_ids = {
                r[0]
                for r in session.query(Activity.activity_id)
                .filter(Activity.activity_id.in_(fetched_ids))
                .all()
            }

            new_activities = [
                a
                for a in runs_only
                if int(a.get("id") or a.get("activity_id")) not in existing_ids
            ]
            for a in new_activities:
                a["activity_id"] = a.pop("id", None) or a.get("activity_id")
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
        else:
            logger.info(
                "No new runs found from Strava API (activities may already exist)"
            )

        sync_progress(
            60,
            "Saving activities",
            detail=f"Saved {inserted_count} new runs",
        )

        # ALWAYS run enrichment if date range is provided, even if no new activities were synced
        # This ensures existing activities in the date range get enriched
        should_enrich = True
        if after is None and before is None:
            # Only skip enrichment if no date range provided AND no activities were synced
            should_enrich = inserted_count > 0

        if should_enrich:
            logger.info("Enriching activities...")
            print(
                f"🔄 [Orchestrator] About to call run_enrichment_batch with: "
                f"athlete_id={athlete_id}, batch_size={batch_size}, "
                f"after={after}, before={before}",
                flush=True,
            )

            try:
                enriched = (
                    run_enrichment_batch(
                        session,
                        athlete_id,
                        batch_size=batch_size,
                        split_cutoff=two_week_cutoff_dt,
                        after=after,  # Pass date range to enrichment
                        before=before,  # Pass date range to enrichment
                    )
                    or 0
                )
                print(
                    f"✅ [Orchestrator] run_enrichment_batch returned: enriched={enriched}",
                    flush=True,
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
        else:
            logger.info(
                "Skipping enrichment (no date range provided and no new activities)"
            )
            enriched = 0

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
