#!/usr/bin/env python3
import os
import time
import logging
import argparse
import sqlite3
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from db import enrich_activity_pg, get_conn, save_token_pg, get_tokens_pg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def get_valid_access_token(client_id, client_secret, athlete_id):
    tokens = get_tokens_pg(athlete_id)
    if not tokens:
        raise RuntimeError(f"No tokens for athlete {athlete_id}")
    access, refresh = tokens["access_token"], tokens["refresh_token"]

    # Quick test call to see if it’s expired
    resp = requests.get(
        "https://www.strava.com/api/v3/athlete",
        headers={"Authorization": f"Bearer {access}"}
    )
    if resp.status_code == 401:
        logging.info("🔁 Refreshing token for athlete %s", athlete_id)
        r2 = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id":     client_id,
                "client_secret": client_secret,
                "grant_type":    "refresh_token",
                "refresh_token": refresh
            }
        )
        r2.raise_for_status()
        d = r2.json()
        access, refresh = d["access_token"], d["refresh_token"]
        save_token_pg(athlete_id, access, refresh)

    return access

def fetch_all_activity_ids(conn, athlete_id):
    cur = conn.cursor()
    # both SQLite and Postgres support a simple SELECT here
    cur.execute("SELECT activity_id FROM activities WHERE athlete_id = %s ORDER BY start_date;" if isinstance(conn, psycopg2.extensions.connection)
                else "SELECT activity_id FROM activities WHERE athlete_id = ? ORDER BY start_date;",
                (athlete_id,))
    return [row[0] for row in cur.fetchall()]

def enrich_all(athlete_id, client_id, client_secret, delay, retries):
    # 1) open DB
    conn = get_conn()
    ids = fetch_all_activity_ids(conn, athlete_id)
    conn.close()

    logging.info("Will enrich %d activities for athlete %s", len(ids), athlete_id)
    token = get_valid_access_token(client_id, client_secret, athlete_id)

    for aid in ids:
        for attempt in range(1, retries + 2):
            logging.info("Enriching activity %s (try %s)…", aid, attempt)
            r = requests.get(
                f"https://www.strava.com/api/v3/activities/{aid}?include_all_efforts=true",
                headers={"Authorization": f"Bearer {token}"}
            )
            if r.status_code == 200:
                enrich_activity_pg(aid, r.json())
                break
            elif r.status_code == 429:
                backoff = delay * (2 ** (attempt - 1))
                logging.warning(" → 429 hit; waiting %ss then retry", backoff)
                time.sleep(backoff)
                continue
            else:
                r.raise_for_status()
        else:
            logging.error("❌ Failed to enrich %s after %s retries", aid, retries)

        time.sleep(delay)

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Backfill all activities with full details from Strava"
    )
    p.add_argument("athlete_id", type=int)
    p.add_argument("--client-id",     required=True)
    p.add_argument("--client-secret", required=True)
    p.add_argument(
        "--delay", type=int, default=12,
        help="Seconds to wait between calls (default 12)"
    )
    p.add_argument(
        "--retries", type=int, default=3,
        help="How many times to retry on 429 (default 3)"
    )
    args = p.parse_args()

    enrich_all(
        args.athlete_id,
        args.client_id,
        args.client_secret,
        args.delay,
        args.retries
    )
