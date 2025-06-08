# src/services/activity_ingestion_service.py

from datetime import datetime, timedelta
from src.services.strava_client import StravaClient
from src.db.dao.activity_dao import upsert_activities
from src.services.token_service import get_valid_token
from src.utils.logger import get_logger

log = get_logger(__name__)

DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_PER_PAGE = 200

class ActivityIngestionService:

    def __init__(self, session, athlete_id):
        self.session = session
        self.athlete_id = athlete_id

        self.access_token = get_valid_token(session, athlete_id)
        self.client = StravaClient(self.access_token)

    def ingest_recent(self, lookback_days=DEFAULT_LOOKBACK_DAYS, max_activities=None):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)
        return self.ingest_between(start_date, end_date, max_activities)

    def ingest_full_history(self, lookback_days=365, max_activities=None):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)
        return self.ingest_between(start_date, end_date, max_activities)

    def ingest_between(self, start_date, end_date, max_activities=None):
        all_activities = []
        page = 1

        while True:
            activities = self.client.get_activities(
                after=int(start_date.timestamp()),
                before=int(end_date.timestamp()),
                page=page,
                per_page=DEFAULT_PER_PAGE
            )

            if not activities:
                break

            all_activities.extend(activities)
            if max_activities and len(all_activities) >= max_activities:
                break

            page += 1

        if max_activities:
            all_activities = all_activities[:max_activities]

        activity_count = upsert_activities(self.session, self.athlete_id, all_activities)

        # 🚫 TEMPORARILY DISABLING SPLITS INGESTION TO AVOID STRAVA RATE LIMITS
        log.info(f"✅ Ingested {activity_count} activities (splits skipped during testing)")

        return activity_count
