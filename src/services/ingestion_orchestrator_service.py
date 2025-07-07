import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import exists

sys.path.append(str(Path(__file__).resolve().parents[2]))  # adds project root

from src.db.dao.activity_dao import ActivityDAO
from src.utils.logger import get_logger
from src.services.activity_service import (
    ActivityIngestionService,
    enrich_one_activity_with_refresh,
    run_enrichment_batch,
)
from src.db.dao.token_dao import get_tokens_sa
from src.services.token_service import get_valid_token
from src.db.models.activities import Activity
from src.db.models.tokens import Token
from src.utils.seeder import seed_sample_activity

logger = get_logger(__name__)

def run_full_ingestion_and_enrichment(session, athlete_id):
    logger.info(f"[CRON SYNC] ✅ Sync job started at {datetime.utcnow().isoformat()}")
    logger.info(f"🚀 Starting run_full_ingestion_and_enrichment for athlete {athlete_id}")

    tokens = get_tokens_sa(session, athlete_id)
    if not tokens:
        logger.warning(f"⚠️ No tokens found for athlete {athlete_id}. Attempting to seed from .env...")

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
            logger.info(f"✅ Seeded Strava token from .env for athlete {athlete_id}")
        else:
            logger.warning("⚠️ .env credentials not found. Using fallback seeding for mock activity")
            seed_sample_activity(session, athlete_id)
            session.commit()
            logger.info(f"✅ Seeded mock activity for athlete {athlete_id}")
            return {"synced": 1, "enriched": 0}

    access_token = get_valid_token(session, athlete_id)
    logger.info(f"🟢 Retrieved valid access token for athlete {athlete_id}")

    logger.info(f"🗖️ Fetching recent activities from Strava...")
    service = ActivityIngestionService(session, athlete_id)

    # 👇 Force override: pull last 10 activities, NOT by date
    after_ts = None
    max_activities = 10
    per_page = 15
    batch_size = 10

    all_fetched = service.client.get_activities(after=after_ts, per_page=per_page, limit=max_activities)
    all_fetched = [a for a in all_fetched if a.get("type") == "Run"]

    if not all_fetched:
        logger.info("📬 No activities returned from Strava.")
        return {"synced": 0, "enriched": 0}

    fetched_ids = [a["id"] for a in all_fetched]
    existing_ids = {r[0] for r in session.query(Activity.activity_id).filter(Activity.activity_id.in_(fetched_ids)).all()}
    new_activities = [a for a in all_fetched if a["id"] not in existing_ids]

    if not new_activities:
        logger.info("✅ All activities from Strava already exist in the database.")
        return {"synced": 0, "enriched": 0}

    logger.info(f"⬇️ Ingesting {len(new_activities)} new activities...")
    ActivityDAO.upsert_activities(session, athlete_id, new_activities)
    logger.info(f"✅ Synced {len(new_activities)} activities")

    enriched = run_enrichment_batch(session, athlete_id, batch_size=batch_size)
    logger.info(f"✅ Enriched {enriched} activities")

    logger.info(f"🎯 Ingestion + enrichment complete for athlete {athlete_id}")
    return {"synced": len(new_activities), "enriched": enriched}

def ingest_specific_activity(session, athlete_id, activity_id):
    logger.info(f"⏳ Ingesting specific activity {activity_id} for athlete {athlete_id}")
    service = ActivityIngestionService(session, athlete_id)
    activity_data = service.client.get_activity(activity_id)
    if not activity_data:
        logger.warning(f"Activity {activity_id} not found for athlete {athlete_id}")
        return 0

    ActivityDAO.upsert_activities(session, athlete_id, [activity_data])
    logger.info(f"✅ Activity {activity_id} upserted")

    try:
        enrich_one_activity_with_refresh(session, athlete_id, activity_id)
        logger.info(f"✅ Activity {activity_id} enriched")
    except Exception as e:
        logger.error(f"❌ Skipping enrichment for activity {activity_id} due to error: {e}")

    return 1

def ingest_between_dates(session, athlete_id, start_date: datetime, end_date: datetime, batch_size=10, max_activities=None, per_page=200):
    logger.info(f"⏳ Ingesting activities for athlete {athlete_id} between {start_date} and {end_date}")
    service = ActivityIngestionService(session, athlete_id)
    activities = service.client.get_activities(
        after=int(start_date.timestamp()),
        before=int(end_date.timestamp()),
        per_page=per_page,
        limit=max_activities
    )

    activities = [a for a in activities if a.get("type") == "Run"]

    if not activities:
        logger.warning(f"No Run activities found between dates for athlete {athlete_id}")
        return 0

    ActivityDAO.upsert_activities(session, athlete_id, activities)
    logger.info(f"✅ Upserted {len(activities)} activities")

    count = 0
    for act in activities:
        try:
            enrich_one_activity_with_refresh(session, athlete_id, act["id"])
            count += 1
            if count % batch_size == 0:
                logger.info(f"Processed {count} activities for enrichment")
        except Exception:
            continue

    logger.info(f"✅ Enriched {count} activities")
    return count

def ingest_today(session, athlete_id):
    today = datetime.utcnow()
    start = datetime(today.year, today.month, today.day)
    end = start + timedelta(days=1)
    return ingest_between_dates(session, athlete_id, start_date=start, end_date=end)
