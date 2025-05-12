#!/usr/bin/env python3
import time
import logging
import requests
import argparse
import sys

from db import get_conn
from app import get_valid_access_token, enrich_activity_pg

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Defaults
BASE_DELAY  = 10   # seconds between successful calls
MAX_RETRIES = 3    # retries per activity on 429

def enrich_all(athlete_id, base_delay, max_retries):
    # 1) Get a valid access token (refreshes automatically)
    token = get_valid_access_token(athlete_id)

    # 2) Load all activity IDs from the DB
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT activity_id FROM activities WHERE athlete_id = %s", (athlete_id,))
    ids = [row[0] for row in cur.fetchall()]
    conn.close()

    logging.info("Will enrich %d activities for athlete %d", len(ids), athlete_id)

    count = 0
    for aid in ids:
        tries = 0
        while tries < max_retries:
            logging.info("Enriching activity %d (try %d)…", aid, tries + 1)
            resp = requests.get(
                f"https://www.strava.com/api/v3/activities/{aid}?include_all_efforts=true",
                headers={"Authorization": f"Bearer {token}"}
            )

            if resp.status_code == 200:
                enrich_activity_pg(aid, resp.json())
                count += 1
                logging.info(" → Success; sleeping %ds", base_delay)
                time.sleep(base_delay)
                break

            if resp.status_code == 429:
                # obey Retry-After or exponential backoff
                ra = resp.headers.get("Retry-After")
                ra = int(ra) if ra and ra.isdigit() else base_delay
                backoff = base_delay * (2 ** tries)
                wait = max(ra, backoff)
                logging.warning(" → 429 hit; waiting %ds then retry", wait)
                time.sleep(wait)
                tries += 1
                continue

            logging.warning(" → Skipped %d: HTTP %d", aid, resp.status_code)
            break
        else:
            logging.error(" → Giving up on %d after %d retries", aid, max_retries)

    logging.info("🎉 Enrichment complete: %d activities updated.", count)


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Backfill Enrichment: fetch full Strava details for every activity."
    )
    p.add_argument("athlete_id", type=int, help="Your Strava athlete ID")
    p.add_argument("--db-url",    required=True,
                   help="Postgres DATABASE_URL (e.g. postgresql://user:pass@host:port/db)")
    p.add_argument("--client-id", required=True, help="STRAVA_CLIENT_ID")
    p.add_argument("--client-secret", required=True, help="STRAVA_CLIENT_SECRET")
    p.add_argument("--delay", "-d", type=int, default=BASE_DELAY,
                   help="Seconds to wait after each successful call")
    p.add_argument("--retries", "-r", type=int, default=MAX_RETRIES,
                   help="Retries per activity on 429")
    args = p.parse_args()

    # Temporarily inject into os.environ so get_conn() and get_valid_access_token() work
    import os
    os.environ["DATABASE_URL"]         = args.db_url
    os.environ["STRAVA_CLIENT_ID"]     = args.client_id
    os.environ["STRAVA_CLIENT_SECRET"] = args.client_secret

    enrich_all(args.athlete_id, args.delay, args.retries)
