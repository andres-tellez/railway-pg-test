### activity_service.py

import time
import json
import logging
import os
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.db.dao.split_dao import upsert_splits
from src.db.dao.activity_dao import ActivityDAO
from src.services.strava_access_service import StravaClient
from src.utils.logger import get_logger
import src.utils.config as config
from src.utils.conversions import convert_metrics
from src.db.models.activities import Activity

log = get_logger(__name__)
log.setLevel(logging.INFO)


def log_strava_payload(activity_id, activity_json, zones_data, streams):
    try:
        os.makedirs("debug_dumps", exist_ok=True)
        with open(f"debug_dumps/strava_debug_{activity_id}.json", "w") as f:
            json.dump({
                "activity": activity_json,
                "zones": zones_data,
                "streams": streams
            }, f, indent=2)
    except Exception as e:
        log.warning(f"⚠️ Could not write debug payload for {activity_id}: {e}")


def get_activities_to_enrich(session, athlete_id, limit):
    result = session.execute(
        text("""
            SELECT activity_id FROM activities
            WHERE athlete_id = :athlete_id AND type = 'Run'
            ORDER BY start_date DESC
            LIMIT :limit
        """),
        {"athlete_id": athlete_id, "limit": limit}
    )
    return [row.activity_id for row in result.fetchall()]


def enrich_one_activity(session, access_token, activity_id):
    try:
        client = StravaClient(access_token)
        required_fields = ["distance", "moving_time", "average_speed", "name"]
        soft_fields = ["average_heartrate", "suffer_score", "max_speed", "calories"]

        activity_json = client.get_activity(activity_id)
        zones_data = client.get_hr_zones(activity_id)
        streams = client.get_streams(activity_id, keys=["distance", "time", "velocity_smooth", "heartrate"])

        if not all(activity_json.get(field) for field in required_fields):
            raise ValueError(f"Missing critical data for {activity_id}")

        log_strava_payload(activity_id, activity_json, zones_data, streams)

        missing_soft = [f for f in soft_fields if activity_json.get(f) is None]
        if missing_soft:
            log.debug(f"Partial enrichment for activity {activity_id} — missing: {missing_soft}")

        log.info(f"➡️ Enriching activity {activity_id} — {activity_json.get('name')}")
        hr_zone_pcts = extract_hr_zone_percentages(zones_data) or [0.0] * 5
        update_activity_enrichment(session, activity_id, activity_json, hr_zone_pcts)

        splits = build_mile_splits(activity_id, streams)
        if splits:
            upsert_splits(session, splits)
            log.info(f"✅ Synced {len(splits)} splits for activity {activity_id}")

        return True
    except Exception as e:
        if "404" in str(e):
            log.warning(f"404 error: Activity {activity_id} not found on Strava")
        else:
            log.error(f"Enrichment failed for {activity_id}: {e}")
        raise


def enrich_one_activity_with_refresh(session, athlete_id, activity_id):
    try:
        access_token = get_valid_token(session, athlete_id)
        enrich_one_activity(session, access_token, activity_id)
        session.expire_all()
        return True
    except Exception as e:
        log.warning(f"Skipping enrichment for activity {activity_id} due to: {e}")
        return False


# --- rest of the functions (update_activity_enrichment, extract_hr_zone_percentages, build_mile_splits) remain unchanged ---


### token_service.py

import logging
import requests

from datetime import datetime, timedelta

import src.utils.config as config
from src.db.dao.token_dao import get_tokens_sa, insert_token_sa, delete_tokens_sa

logger = logging.getLogger(__name__)


def is_expired(expires_at):
    return expires_at <= int(datetime.utcnow().timestamp())


def get_valid_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    if is_expired(token_data["expires_at"]):
        return refresh_access_token(session, athlete_id)["access_token"]

    return token_data["access_token"]


def refresh_access_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No refresh token available for athlete {athlete_id}")

    tokens = refresh_token_static(token_data["refresh_token"])
    insert_token_sa(
        session=session,
        athlete_id=athlete_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"]
    )
    return tokens


def refresh_token_static(refresh_token):
    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    response.raise_for_status()
    return response.json()


### ingestion_orchestration_service.py

from src.db.dao.activity_dao import ActivityDAO
from src.utils.logger import get_logger

from src.db.dao.token_dao import get_tokens_sa

from src.db.models.activities import Activity
from src.utils.seeder import seed_sample_activity

logger = get_logger(__name__)


def ingest_between_dates(session, athlete_id, start_date, end_date, batch_size=10, max_activities=None, per_page=200):
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

    enriched_count = 0
    for act in activities:
        success = enrich_one_activity_with_refresh(session, athlete_id, act["id"])
        if success:
            enriched_count += 1
        if enriched_count % batch_size == 0:
            logger.info(f"Processed {enriched_count} activities")

    logger.info(f"✅ Enriched {enriched_count} activities")
    return enriched_count
