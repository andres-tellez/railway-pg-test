import os
import time
import logging
import requests
import traceback
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from src.db.db_session import get_session
from src.routes.enrich import enrich_activity_pg
from src.services.strava import refresh_strava_token
from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("enrichment_worker")

# Enrichment Config
DEFAULT_BATCH_SIZE = 20
DEFAULT_RETRY_LIMIT = 5
DEFAULT_SLEEP = 5
DEFAULT_RETRY_BACKOFF = 2

STRAVA_URL = "https://www.strava.com/api/v3/activities/{activity_id}?include_all_efforts=true"


def get_valid_access_token(session, athlete_id):
    tokens = get_tokens_sa(session, athlete_id)
    if not tokens:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    now_ts = int(time.time())
    token_row = session.query_token(athlete_id)

    if token_row.expires_at > now_ts:
        return tokens["access_token"]

    refreshed = refresh_strava_token(tokens["refresh_token"])
    save_tokens_sa(session, athlete_id, refreshed["access_token"], refreshed["refresh_token"], refreshed["expires_at"])
    return refreshed["access_token"]


def get_activities_to_enrich(session, athlete_id, limit):
    query = text("""
        SELECT activity_id FROM activities
        WHERE athlete_id = :athlete_id
        ORDER BY start_date DESC
        LIMIT :limit
    """)
    result = session.execute(query, {"athlete_id": athlete_id, "limit": limit})
    return [row.activity_id for row in result.fetchall()]


def enrich_one_activity(session, athlete_id, access_token, activity_id):
    try:
        url = STRAVA_URL.format(activity_id=activity_id)
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            activity_json = resp.json()
            enrich_activity_pg(activity_id, activity_json)
            log.info(f"✅ Enriched activity {activity_id}")
            return True

        elif resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", DEFAULT_SLEEP))
            log.warning(f"⚠️ 429 Rate Limited. Retry-After: {retry_after}s")
            time.sleep(retry_after)
            return False

        else:
            log.error(f"❌ Failed to enrich {activity_id} — HTTP {resp.status_code}")
            return True  # skip this activity

    except Exception as e:
        log.error(f"🔥 Exception while enriching {activity_id}: {e}")
        traceback.print_exc()
        return True  # skip this activity


def enrichment_loop(athlete_id, batch_size=DEFAULT_BATCH_SIZE):
    session = get_session()
    try:
        access_token = get_valid_access_token(session, athlete_id)
        activities = get_activities_to_enrich(session, athlete_id, batch_size)

        log.info(f"🌀 Enriching {len(activities)} activities for athlete {athlete_id}")
        
        for activity_id in activities:
            retries = 0
            while retries < DEFAULT_RETRY_LIMIT:
                success = enrich_one_activity(session, athlete_id, access_token, activity_id)
                if success:
                    break  # either succeeded or failed permanently
                retries += 1
                time.sleep(DEFAULT_SLEEP * (DEFAULT_RETRY_BACKOFF ** retries))

    except SQLAlchemyError as db_err:
        log.error(f"DB error during enrichment: {db_err}")
        session.rollback()

    except Exception as e:
        log.error(f"Unexpected enrichment failure: {e}")
        traceback.print_exc()

    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enrichment Worker")
    parser.add_argument("athlete_id", type=int, help="Strava athlete ID to enrich")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH_SIZE, help="Max activities to enrich")
    args = parser.parse_args()

    enrichment_loop(args.athlete_id, batch_size=args.batch)
