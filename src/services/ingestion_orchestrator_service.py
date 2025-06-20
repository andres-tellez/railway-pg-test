from datetime import datetime
from src.db.dao.activity_dao import ActivityDAO
from src.utils.logger import get_logger
from src.services.activity_service import ActivityIngestionService, enrich_one_activity_with_refresh


logger = get_logger(__name__)

def ingest_specific_activity(session, athlete_id, activity_id):
    logger.info(f"⏳ Ingesting specific activity {activity_id} for athlete {athlete_id}")
    service = ActivityIngestionService(session, athlete_id)
    # Get single activity details from Strava client
    activity_data = service.client.get_activity(activity_id)
    if not activity_data:
        logger.warning(f"Activity {activity_id} not found for athlete {athlete_id}")
        return 0

    # Upsert activity using DAO
    ActivityDAO.upsert_activities(session, athlete_id, [activity_data])
    logger.info(f"✅ Activity {activity_id} upserted")

    # Enrich activity
    enrich_one_activity_with_refresh(session, athlete_id, activity_id)
    logger.info(f"✅ Activity {activity_id} enriched")

    return 1


def ingest_between_dates(session, athlete_id, start_date: datetime, end_date: datetime, batch_size=10):
    logger.info(f"⏳ Ingesting activities for athlete {athlete_id} between {start_date} and {end_date}")
    service = ActivityIngestionService(session, athlete_id)
    activities = service.client.get_activities(
        after=int(start_date.timestamp()),
        before=int(end_date.timestamp())
    )

    if not activities:
        logger.warning(f"No activities found between dates for athlete {athlete_id}")
        return 0

    ActivityDAO.upsert_activities(session, athlete_id, activities)
    logger.info(f"✅ Upserted {len(activities)} activities")

    # Enrich in batches for performance
    count = 0
    for act in activities:
        enrich_one_activity_with_refresh(session, athlete_id, act["id"])
        count += 1
        if count % batch_size == 0:
            logger.info(f"Processed {count} activities for enrichment")

    logger.info(f"✅ Enriched {count} activities")

    return count
