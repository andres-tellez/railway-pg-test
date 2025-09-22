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
from src.utils.seeder import seed_sample_activity
from src.routes.progress import set_progress  # ✅ in-memory progress tracker
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
):
    session = get_session()

    def progress(stage, message="", current=0, total=0, percent=None):
        """Normalize backend stages into frontend-friendly buckets (UI uses user_id)."""
        stage_map = {
            "auth_ok": "fetching",
            "compute_window": "fetching",
            "fetch_start": "fetching",
            "fetch_done": "fetching",
            "filter_done": "fetching",
            "upsert_start": "fetching",
            "upsert_done": "fetching",
            "enrich_start": "enriching",
            "enrich_done": "enriching",
        }
        ui_stage = stage_map.get(stage, stage)

        try:
            if percent is None:
                percent = (current / total * 100.0) if total else 0.0
            if user_id:  # ✅ progress now keyed by user_id
                logger.info(
                    f"[Progress] user_id={user_id} | stage={ui_stage} | "
                    f"message='{message}' | percent={percent:.1f}"
                )
                set_progress(str(user_id), ui_stage, message, percent)
        except Exception:
            logger.exception("Progress reporting failed (non-fatal)")

    try:
        logger.info(
            f"[CRON SYNC] ✅ Sync job started at {datetime.utcnow().isoformat()} for user_id={user_id}, athlete_id={athlete_id}"
        )
        progress("starting", "Starting sync with Strava…", percent=2)

        # -------------------------
        # Artificial delay for demo UX
        # Remove these sleeps in production
        import time

        time.sleep(2)
        # -------------------------

        max_activities = max_activities or 200
        batch_size = batch_size or min(200, 50)
        per_page = per_page or min(200, 50)

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
                progress("done", "Mock activity seeded", percent=100)
                return {"synced": 1, "enriched": 0}

        access_token = get_valid_token(session, athlete_id)
        progress("auth_ok", "Access granted ✅", percent=8)

        time.sleep(1)  # ⏳ simulate auth step

        after = after or int(
            (datetime.utcnow() - timedelta(days=lookback_days))
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        before = before or int(
            datetime.utcnow()
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        progress("compute_window", "Preparing date window", percent=12)

        time.sleep(1)  # ⏳ simulate compute window

        service = ActivityIngestionService(session, athlete_id)
        progress("fetch_start", "Fetching recent runs from Strava…", percent=18)

        time.sleep(2)  # ⏳ simulate network fetch

        try:
            all_fetched = service.client.get_activities(
                after=after, before=before, per_page=per_page, limit=max_activities
            )
        except Exception as e:
            progress("error", f"Failed to fetch: {e}")
            return {"synced": 0, "enriched": 0}

        progress(
            "fetch_done",
            f"Fetched {len(all_fetched)} activities",
            current=len(all_fetched),
            total=len(all_fetched),
            percent=30,
        )

        time.sleep(1)

        runs_only = [a for a in all_fetched if a.get("type") == "Run"]
        progress(
            "filter_done",
            f"Identified {len(runs_only)} runs",
            current=len(runs_only),
            total=len(all_fetched),
            percent=36,
        )

        if not runs_only:
            progress("done", "No runs found in Strava account", percent=100)
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
            a["user_id"] = user_id  # ✅ store user_id (UUID) alongside activity

        # Deduplicate by activity_id
        dedup = {
            int(a["activity_id"]): a for a in new_activities if a.get("activity_id")
        }
        unique_new_activities = list(dedup.values())

        progress(
            "upsert_start",
            f"Saving {len(unique_new_activities)} runs…",
            total=len(unique_new_activities),
            percent=45,
        )

        time.sleep(1)

        inserted_count = ActivityDAO.upsert_activities(
            session, athlete_id, unique_new_activities, user_id=user_id
        )

        progress(
            "upsert_done",
            f"Synced {inserted_count} new runs",
            current=inserted_count,
            total=len(unique_new_activities),
            percent=65,
        )

        time.sleep(1)

        progress("enrich_start", "Enriching activities…", percent=75)

        time.sleep(2)  # ⏳ simulate enrichment step

        try:
            enriched = (
                run_enrichment_batch(session, athlete_id, batch_size=batch_size) or 0
            )
            progress("enrich_done", f"Enriched {enriched} activities ✅", percent=90)
        except Exception as e:
            progress("error", f"Enrichment failed: {e}", percent=90)
            enriched = 0

        progress(
            "done",
            f"Finished. Synced={inserted_count}, Enriched={enriched}",
            percent=100,
        )
        return {"synced": inserted_count, "enriched": enriched}

    except Exception as e:
        session.rollback()
        logger.exception(f"❌ Ingestion failed: {e}")
        progress("error", f"Ingestion failed: {e}", percent=0)
        return {"synced": 0, "enriched": 0}
    finally:
        session.close()
