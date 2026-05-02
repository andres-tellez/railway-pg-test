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
- Full: Fetches activities from Strava within the ingest lookback window (first sync or force flag); see `STRAVA_INGEST_LOOKBACK_WEEKS` in `strava_reconciliation_service`

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
from datetime import datetime, timedelta, timezone

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
from src.utils.rate_limiter import get_rate_limiter
from src.services.strava_reconciliation_service import (
    STRAVA_INGEST_LOOKBACK_WEEKS,
    compute_strava_six_week_window,
    filter_strava_runs_in_six_week_window,
)
from src.services.strava_sync_retry_service import schedule_strava_ingestion_retry
from src.db.dao.strava_ingestion_retry_dao import delete_retry_standalone
from src.services.run_execution_analysis_service import analyze_recent_activity_window

logger = logging.getLogger(__name__)

# Automatic retries when Strava API headroom is too low (see rate-limit check below).
MAX_SYNC_AUTO_RETRIES = 5

# Fetch + enrich in segments so headroom is checked per segment (~2 weeks).
STRAVA_SYNC_CHUNK_SECONDS = 14 * 24 * 60 * 60

USER_MSG_HEADROOM_DEFERRED = (
    "Strava is extra busy right now, so we paused your run import on purpose — "
    "that avoids broken or partial data. SmartCoach will try again automatically in a few minutes. "
    "You can keep using the app and chatting with your coach in the meantime."
)

USER_MSG_HEADROOM_EXHAUSTED = (
    "We couldn't finish importing your runs after several automatic tries because "
    "Strava's API has been very busy. Please try again in an hour, or disconnect and reconnect Strava "
    "from your profile. Your account is otherwise fine."
)

USER_MSG_GENERIC_SYNC_FAILURE = (
    "Something went wrong while importing your runs from Strava. "
    "Please try again in a little while. If this keeps happening, reconnect Strava from your profile."
)


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
    sync_retry_attempt=0,
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
        sync_retry_attempt: Internal counter for automatic headroom retries (default: 0)

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
            delete_retry_standalone(str(user_id), int(athlete_id))
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to mark sync complete: %s", exc)

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

        win = compute_strava_six_week_window()
        six_week_start_dt = win.six_week_start_dt
        two_week_cutoff_dt = win.two_week_cutoff_dt
        window_after_ts = win.window_after_ts
        now_ts = win.before_ts

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
                f"🔄 Full sync: fetching activities from {six_week_start_dt.isoformat()} "
                f"(last {STRAVA_INGEST_LOOKBACK_WEEKS} full weeks + current week)"
            )

        print("[INGEST_DEBUG] SYNC MODE")
        print("use_incremental:", use_incremental)
        print("final_after_ts:", after_ts)

        logger.info(
            "Prepared date window: after=%s, before=%s",
            datetime.fromtimestamp(after_ts, tz=timezone.utc).isoformat(),
            datetime.fromtimestamp(before_ts, tz=timezone.utc).isoformat(),
        )

        chunk_boundaries: list[tuple[int, int]] = []
        ca = after_ts
        while ca < before_ts:
            cb = min(ca + STRAVA_SYNC_CHUNK_SECONDS, before_ts)
            chunk_boundaries.append((ca, cb))
            ca = cb

        if not chunk_boundaries:
            logger.warning(
                "Empty Strava sync window (after_ts >= before_ts); skipping fetch"
            )
            sync_progress(75, "Nothing to sync")
            update_last_sync_timestamp(session, athlete_id)
            sync_complete()
            return {"synced": 0, "enriched": 0}

        num_chunks = len(chunk_boundaries)
        if num_chunks > 1:
            logger.info(
                "Splitting Strava sync into %d chunk(s) of up to %d days each "
                "(headroom + success rate).",
                num_chunks,
                STRAVA_SYNC_CHUNK_SECONDS // 86400,
            )

        service = ActivityIngestionService(session, athlete_id)
        total_inserted = 0
        total_enriched = 0
        total_analyzed = 0

        for idx, (chunk_after, chunk_before) in enumerate(chunk_boundaries):
            fetch_pct = 20.0 + (idx / num_chunks) * 15.0
            sync_progress(
                fetch_pct,
                "Fetching activities from Strava…",
                detail=(
                    f"Chunk {idx + 1}/{num_chunks}: "
                    f"{datetime.fromtimestamp(chunk_after, tz=timezone.utc).date()} → "
                    f"{datetime.fromtimestamp(chunk_before, tz=timezone.utc).date()}"
                ),
            )
            logger.info(
                "Fetching Strava runs chunk %d/%d after=%s before=%s",
                idx + 1,
                num_chunks,
                datetime.fromtimestamp(chunk_after, tz=timezone.utc).isoformat(),
                datetime.fromtimestamp(chunk_before, tz=timezone.utc).isoformat(),
            )

            try:
                all_fetched = service.fetch_all_activities(
                    after=chunk_after,
                    before=chunk_before,
                    per_page=per_page,
                    type_filter="Run",
                    type_limit=None,
                )
                # Backward-compatibility hardening: older tests/services may stub
                # client.get_activities directly instead of fetch_all_activities.
                if not isinstance(all_fetched, list):
                    legacy_get = getattr(
                        getattr(service, "client", None), "get_activities", None
                    )
                    if callable(legacy_get):
                        all_fetched = (
                            legacy_get(
                                after=chunk_after,
                                before=chunk_before,
                                per_page=per_page,
                            )
                            or []
                        )
                    else:
                        all_fetched = []
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

            logger.info(
                "Chunk %d/%d: fetched %d run activities from Strava",
                idx + 1,
                num_chunks,
                len(all_fetched),
            )
            runs_only = filter_strava_runs_in_six_week_window(
                six_week_start_dt, all_fetched
            )

            # Persist new run summaries before enrichment headroom check so a deferral
            # still leaves Strava list data in the DB (ActivityDAO commits per upsert).
            inserted_count = 0
            proc_pct = 35.0 + (idx / num_chunks) * 20.0
            sync_progress(
                proc_pct,
                "Processing activities",
                detail=f"Chunk {idx + 1}/{num_chunks}: {len(runs_only)} runs",
            )
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
                    int(a["activity_id"]): a
                    for a in new_activities
                    if a.get("activity_id")
                }
                unique_new_activities = list(dedup.values())

                logger.info(
                    "Chunk %d/%d: saving %d new runs...",
                    idx + 1,
                    num_chunks,
                    len(unique_new_activities),
                )

                inserted_count = ActivityDAO.upsert_activities(
                    session, athlete_id, unique_new_activities, user_id=user_id
                )

                logger.info(
                    "Chunk %d/%d: synced %d new runs",
                    idx + 1,
                    num_chunks,
                    inserted_count,
                )
            else:
                logger.info(
                    "Chunk %d/%d: no new runs from Strava list (may already exist)",
                    idx + 1,
                    num_chunks,
                )

            total_inserted += inserted_count

            save_pct = 55.0 + (idx / num_chunks) * 10.0
            sync_progress(
                min(save_pct, 65.0),
                "Saving activities",
                detail=f"Chunk {idx + 1}/{num_chunks}: saved {inserted_count} new runs",
            )

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
                "Chunk %d/%d: projected enrichment Strava calls=%d, remaining_15min=%d",
                idx + 1,
                num_chunks,
                projected_enrichment_calls,
                remaining_15m,
            )

            RATE_BUFFER = 10
            if projected_enrichment_calls + RATE_BUFFER > remaining_15m:
                wait_seconds = max(stats.get("wait_time_seconds", 0), 60)
                logger.warning(
                    "Rate limit headroom too low (%d remaining, %d needed). Deferring "
                    "after chunk %d/%d (runs already saved for this chunk). "
                    "(sync_retry_attempt=%s).",
                    remaining_15m,
                    projected_enrichment_calls + RATE_BUFFER,
                    idx + 1,
                    num_chunks,
                    sync_retry_attempt,
                )
                if not user_id:
                    sync_error(
                        USER_MSG_GENERIC_SYNC_FAILURE,
                        error_code="RATE_LIMIT_HEADROOM_NO_USER",
                    )
                    raise StravaIngestionSyncError(
                        athlete_id=athlete_id,
                        reason="rate_limit_headroom_no_user",
                        message=(
                            "Strava is handling a lot of requests right now. "
                            f"Please wait about {int(wait_seconds // 60) + 1} minutes before trying again."
                        ),
                    )
                if sync_retry_attempt >= MAX_SYNC_AUTO_RETRIES:
                    sync_error(
                        USER_MSG_HEADROOM_EXHAUSTED,
                        error_code="RATE_LIMIT_EXHAUSTED",
                    )
                    raise StravaIngestionSyncError(
                        athlete_id=athlete_id,
                        reason="rate_limit_retries_exhausted",
                        message="Strava ingestion retries exhausted",
                    )
                retry_delay = max(float(wait_seconds), 120.0)
                schedule_strava_ingestion_retry(
                    user_id, athlete_id, retry_delay, sync_retry_attempt + 1
                )
                sync_error(
                    USER_MSG_HEADROOM_DEFERRED,
                    error_code="RATE_LIMIT_HEADROOM_DEFERRED",
                )
                return {
                    "synced": total_inserted,
                    "enriched": total_enriched,
                    "deferred": True,
                }

            enrich_after = chunk_after
            enrich_before = chunk_before
            if after is None and before is None:
                if num_chunks > 1:
                    should_enrich = len(runs_only) > 0
                else:
                    should_enrich = inserted_count > 0
            else:
                should_enrich = True

            if should_enrich:
                logger.info(
                    "Chunk %d/%d: enriching (after=%s before=%s)...",
                    idx + 1,
                    num_chunks,
                    enrich_after,
                    enrich_before,
                )
                print(
                    f"🔄 [Orchestrator] run_enrichment_batch chunk {idx + 1}/{num_chunks} "
                    f"athlete_id={athlete_id}, after={enrich_after}, before={enrich_before}",
                    flush=True,
                )

                try:
                    enriched = (
                        run_enrichment_batch(
                            session,
                            athlete_id,
                            batch_size=batch_size,
                            split_cutoff=two_week_cutoff_dt,
                            after=enrich_after,
                            before=enrich_before,
                        )
                        or 0
                    )
                    print(
                        f"✅ [Orchestrator] chunk {idx + 1}/{num_chunks} enriched={enriched}",
                        flush=True,
                    )
                    logger.info(
                        "Chunk %d/%d: enriched %d activities",
                        idx + 1,
                        num_chunks,
                        enriched,
                    )
                except StravaTokenError as e:
                    logger.error(f"Token error during enrichment: {e}", exc_info=True)
                    enriched = 0
                    logger.warning(
                        "Enrichment skipped due to token error, but ingestion continued"
                    )
                except Exception as e:
                    logger.error(f"Enrichment failed: {e}", exc_info=True)
                    enriched = 0
                    logger.warning("Enrichment failed, but ingestion continued")
            else:
                logger.info(
                    "Chunk %d/%d: skipping enrichment (no new rows this chunk)",
                    idx + 1,
                    num_chunks,
                )
                enriched = 0

            total_enriched += enriched

            if user_id and runs_only:
                try:
                    analyzed = analyze_recent_activity_window(
                        session,
                        athlete_id=int(athlete_id),
                        user_id=str(user_id),
                        after_ts=chunk_after,
                        before_ts=chunk_before,
                        limit=max(50, int(len(runs_only) * 2)),
                    )
                    if analyzed:
                        total_analyzed += analyzed
                        logger.info(
                            "Chunk %d/%d: analyzed %d run execution record(s)",
                            idx + 1,
                            num_chunks,
                            analyzed,
                        )
                except Exception:
                    logger.warning(
                        "Run execution analysis failed after chunk %d/%d",
                        idx + 1,
                        num_chunks,
                        exc_info=True,
                    )

            # Always run a lightweight window-scoped pass for this chunk so runs
            # that were already present in DB still get analyzed/matched.
            if user_id:
                try:
                    analyzed_backfill = analyze_recent_activity_window(
                        session,
                        athlete_id=int(athlete_id),
                        user_id=str(user_id),
                        after_ts=chunk_after,
                        before_ts=chunk_before,
                        limit=max(120, int(len(runs_only) * 4) if runs_only else 160),
                    )
                    if analyzed_backfill:
                        total_analyzed += analyzed_backfill
                        logger.info(
                            "Chunk %d/%d: backfill analyzed %d run execution record(s)",
                            idx + 1,
                            num_chunks,
                            analyzed_backfill,
                        )
                except Exception:
                    logger.warning(
                        "Run execution backfill failed after chunk %d/%d",
                        idx + 1,
                        num_chunks,
                        exc_info=True,
                    )

            done_pct = 65.0 + ((idx + 1) / num_chunks) * 15.0
            sync_progress(
                min(done_pct, 79.0),
                "Enrichment progress",
                detail=(
                    f"Chunk {idx + 1}/{num_chunks}: enriched {enriched} "
                    f"(total {total_enriched})"
                ),
            )

        inserted_count = total_inserted
        enriched = total_enriched
        if total_analyzed:
            logger.info(
                "Run execution analysis updated %d record(s) during sync",
                total_analyzed,
            )

        sync_progress(
            80,
            "Enrichment complete",
            detail=f"Enriched {enriched} activities across {num_chunks} chunk(s)",
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
        if user_id:
            try:
                from src.services.weekly_insight_post_ingestion_backfill import (
                    schedule_weekly_insights_after_strava_ingestion,
                )

                schedule_weekly_insights_after_strava_ingestion(
                    str(user_id),
                    force_full_sync=force_full_sync,
                    inserted_count=int(inserted_count or 0),
                )
            except Exception:
                logger.warning(
                    "schedule_weekly_insights_after_strava_ingestion failed",
                    exc_info=True,
                )
        return {"synced": inserted_count, "enriched": enriched}

    except (
        StravaIngestionValidationError,
        StravaIngestionSyncError,
        StravaIngestionEnrichmentError,
    ) as e:
        session.rollback()
        if user_id:
            delete_retry_standalone(str(user_id), int(athlete_id))
        if isinstance(e, StravaIngestionSyncError) and getattr(e, "reason", None) in (
            "rate_limit_retries_exhausted",
            "rate_limit_headroom_no_user",
        ):
            raise
        if isinstance(e, StravaIngestionSyncError):
            logger.warning("Strava ingestion sync error: %s", e, exc_info=True)
            sync_error(USER_MSG_GENERIC_SYNC_FAILURE, error_code="STRAVA_SYNC_ERROR")
        else:
            sync_error(f"Sync failed: {e}", error_code=e.__class__.__name__)
        raise
    except StravaTokenError as e:
        session.rollback()
        if user_id:
            delete_retry_standalone(str(user_id), int(athlete_id))
        logger.exception(f"Token error during ingestion: {e}")
        sync_error(f"Token error during sync: {e.message}", error_code="TOKEN_ERROR")
        raise StravaIngestionSyncError(
            athlete_id=athlete_id if "athlete_id" in locals() else None,
            reason=f"Token error: {e.message}",
            message="Ingestion failed due to token error",
        )
    except Exception as e:
        session.rollback()
        if user_id:
            delete_retry_standalone(str(user_id), int(athlete_id))
        logger.exception(f"Ingestion failed: {e}")
        sync_error(f"Ingestion failed: {e}", error_code="INGESTION_ERROR")
        raise StravaIngestionSyncError(
            athlete_id=athlete_id if "athlete_id" in locals() else None,
            reason=str(e),
            message="Ingestion failed with unexpected error",
        )
    finally:
        session.close()
