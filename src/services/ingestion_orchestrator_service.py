# src/services/ingestion_orchestrator_service.py

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

logger = logging.getLogger(__name__)


def run_full_ingestion_and_enrichment(
    _unused_session,
    athlete_id,
    user_id=None,
    lookback_days=365,
    max_activities=config.MAX_ACTIVITIES_TO_DOWNLOAD,
    batch_size=None,
    per_page=None,
    after=None,
    before=None,
    force_full_sync=False,
):
    session = get_session()

    logger.info(
        f"[Ingestion] run_full_ingestion_and_enrichment called for user_id={user_id}, athlete_id={athlete_id}"
    )

    try:
        logger.info(
            f"[CRON SYNC] Sync job started at {datetime.utcnow().isoformat()} "
            f"for user_id={user_id}, athlete_id={athlete_id}"
        )

        # -------------------------
        # Artificial delay for demo UX
        # Remove these sleeps in production
        time.sleep(2)
        # -------------------------

        max_activities = max_activities or config.MAX_ACTIVITIES_TO_DOWNLOAD
        batch_size = batch_size or min(config.MAX_ACTIVITIES_TO_DOWNLOAD, 50)
        per_page = per_page or min(config.MAX_ACTIVITIES_TO_DOWNLOAD, 50)

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
                return {"synced": 1, "enriched": 0}

        access_token = get_valid_token(session, athlete_id)
        logger.info("Access granted")

        time.sleep(1)  # simulate auth step

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

        time.sleep(1)  # simulate compute window

        service = ActivityIngestionService(session, athlete_id)
        logger.info("Fetching recent runs from Strava...")

        time.sleep(2)  # simulate network fetch

        try:
            all_fetched = service.client.get_activities(
                after=after, before=before, per_page=per_page, limit=max_activities
            )
        except Exception as e:
            logger.error(f"Failed to fetch activities: {e}")
            return {"synced": 0, "enriched": 0}

        logger.info(f"Fetched {len(all_fetched)} activities")

        time.sleep(1)

        runs_only = [a for a in all_fetched if a.get("type") == "Run"]
        logger.info(f"Identified {len(runs_only)} runs")

        if not runs_only:
            logger.info("No runs found in Strava account")
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

        time.sleep(1)

        inserted_count = ActivityDAO.upsert_activities(
            session, athlete_id, unique_new_activities, user_id=user_id
        )

        logger.info(f"Synced {inserted_count} new runs")

        time.sleep(1)

        logger.info("Enriching activities...")

        time.sleep(2)  # simulate enrichment step

        try:
            enriched = (
                run_enrichment_batch(session, athlete_id, batch_size=batch_size) or 0
            )
            logger.info(f"Enriched {enriched} activities")
        except Exception as e:
            logger.error(f"Enrichment failed: {e}")
            enriched = 0

        # Refresh materialized views after successful ingestion
        try:
            from sqlalchemy import text

            session.execute(text("REFRESH MATERIALIZED VIEW mv_athlete_metrics;"))
            session.execute(text("REFRESH MATERIALIZED VIEW mv_longest_runs;"))
            session.commit()
            logger.info("✅ Refreshed materialized views for metrics and longest runs")
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

        logger.info(f"Finished ingestion. Synced={inserted_count}, Enriched={enriched}")
        return {"synced": inserted_count, "enriched": enriched}

    except Exception as e:
        session.rollback()
        logger.exception(f"Ingestion failed: {e}")
        return {"synced": 0, "enriched": 0}
    finally:
        session.close()
