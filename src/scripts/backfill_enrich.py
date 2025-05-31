import os
import time
import logging
import requests
import argparse
from sqlalchemy import text

from src.db.base_model import get_session
from src.routes.enrich import enrich_activity_pg

logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)

def backfill_enrich(athlete_id, delay=10, retries=3):
    token = get_valid_access_token(athlete_id)
    session = get_session()

    result = session.execute(
        text("SELECT activity_id FROM activities WHERE athlete_id = :athlete_id LIMIT 5"),
        {"athlete_id": athlete_id}
    )
    ids = [row[0] for row in result.fetchall()]

    logging.info("Enriching %d activities", len(ids))

    for aid in ids:
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(
                    f"https://www.strava.com/api/v3/activities/{aid}?include_all_efforts=true",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status_code == 200:
                    enrich_activity_pg(aid, resp.json())
                    logging.info("✓ Enriched %d", aid)
                    time.sleep(delay)
                    break
                elif resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", delay * attempt))
                    logging.warning("429 received, sleeping %ds", wait)
                    time.sleep(wait)
                else:
                    logging.warning("Failed to enrich %d (status %d)", aid, resp.status_code)
                    break
            except Exception as e:
                logging.error("Exception on %d: %s", aid, e)
                time.sleep(delay * attempt)
        else:
            logging.error("Giving up on %d after %d attempts", aid, retries)

    logging.info("🎉 Enrichment complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich Strava activities with full data")
    parser.add_argument("athlete_id", type=int, help="Strava athlete ID")
    parser.add_argument("--delay", type=int, default=10, help="Delay in seconds between requests")
    parser.add_argument("--retries", type=int, default=3, help="Max retries on failure/429")
    args = parser.parse_args()

    backfill_enrich(args.athlete_id, args.delay, args.retries)
