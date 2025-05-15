#!/usr/bin/env python3
import os
import time
import logging
import requests
import argparse

from db import get_conn
from src.app import get_valid_access_token, insert_activities

logging.basicConfig(level=logging.INFO)

def backfill(athlete_id, delay):
    # Grab a valid token (refreshing as needed)
    token = get_valid_access_token(athlete_id)
    page, total = 1, 0

    while True:
        logging.info("Fetching page %d…", page)
        resp = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            params={"page": page, "per_page": 200},
            headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break

        logging.info(" → Got %d activities; inserting…", len(batch))
        insert_activities(batch, athlete_id)
        total += len(batch)

        page += 1
        time.sleep(delay)

    logging.info("🎉 Backfill complete: %d activities loaded.", total)


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Backfill ALL Strava activities into your DB."
    )
    p.add_argument("athlete_id", type=int, help="Your Strava athlete ID")
    p.add_argument(
        "--delay", "-d", type=int, default=10,
        help="Seconds to wait between requests (default: 10s)"
    )
    args = p.parse_args()

    # Ensure DATABASE_URL, STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET are set.
    for v in ["DATABASE_URL","STRAVA_CLIENT_ID","STRAVA_CLIENT_SECRET"]:
        if v not in os.environ:
            raise RuntimeError(f"Please set ${v} before running")

    backfill(args.athlete_id, args.delay)
