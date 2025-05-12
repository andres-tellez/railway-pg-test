#!/usr/bin/env python3
import time
import logging
import requests
import argparse
import os
import sys

from db import get_conn
from app import get_valid_access_token, enrich_activity_pg

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)

BASE_DELAY  = 10   # default seconds between calls
MAX_RETRIES = 3    # default retries per activity on 429

def enrich_all(athlete_id, base_delay, max_retries):
    # 1) Get a valid token (refreshes automatically)
    token = get_valid_access_token(athlete_id)

    # 2) Load all activity IDs
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT activity_id FROM activities WHERE athlete_id = %s", (athlete_id,))
    ids = [row[0] for row in cur.fetchall()]
    conn.close()

    logging.info("Will enrich %d activities for athlete %d", len(ids), athlete_id)

    count = 0
    for aid in ids:
        for attempt in range(1, max_retries+1):
            logging.info("Enriching activity %d (try %d)…", aid, attempt)
            try:
                resp = requests.get(
                    f"https://www.strava.com/api/v3/activities/{aid}?include_all_efforts=true",
                    headers={"Authorization": f"Bearer {token}"}
                )
            except Exception as e:
                logging.warning("  → network error: %s", e)
                wait = base_delay * attempt
                logging.info("  → sleeping %ds before retry", wait)
                time.sleep(wait)
                continue

            if resp.status_code == 200:
                enrich_activity_pg(aid, resp.json())
                count += 1
                logging.info("  → success; sleeping %ds", base_delay)
                time.sleep(base_delay)
                break

            if resp.status_code == 429:
                ra = resp.headers.get("Retry-After")
                ra = int(ra) if ra and ra.isdigit() else base_delay
                wait = max(ra, base_delay * attempt)
                logging.warning("  → 429 rate-limit; sleeping %ds then retry", wait)
                time.sleep(wait)
                continue

            logging.warning("  → skipped %d (HTTP %d)", aid, resp.status_code)
            break
        else:
            logging.error("  → giving up on %d after %d retries", aid, max_retries)

    logging.info("🎉 Enrichment complete: %d activities updated.", count)


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Backfill Enrichment: fetch full Strava details for every activity."
    )
    p.add_argument("athlete_id", type=int, help="Your Strava athlete ID")
    p.add_argument("--db-url",        required=True, help="Postgres DATABASE_URL")
    p.add_argument("--client-id",     required=True, help="STRAVA_CLIENT_ID")
    p.add_argument("--client-secret", required=True, help="STRAVA_CLIENT_SECRET")
    p.add_argument("--delay",   "-d", type=int, default=BASE_DELAY,  help="Seconds between calls")
    p.add_argument("--retries","-r", type=int, default=MAX_RETRIES, help="Retries per item on 429")

    args = p.parse_args()

    # Inject into env so get_conn() & get_valid_access_token() will pick them up
    os.environ["DATABASE_URL"]         = args.db_url
    os.environ["STRAVA_CLIENT_ID"]     = args.client_id
    os.environ["STRAVA_CLIENT_SECRET"] = args.client_secret
    # force production mode to use Postgres
    os.environ["FLASK_ENV"]            = "production"

    enrich_all(args.athlete_id, args.delay, args.retries)
