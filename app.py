import os
import json
import logging
import requests
import sqlite3
from io import BytesIO
from psycopg2.extras import RealDictCursor

import csv
import traceback
import pandas as pd


from flask import Flask, redirect, request, jsonify, send_file
from psycopg2.extras import RealDictCursor

from db import (
    get_conn,
    save_token_pg,
    get_tokens_pg,
    save_activity_pg,
    enrich_activity_pg,
    save_run_splits,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

CLIENT_ID       = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET   = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI    = os.getenv("REDIRECT_URI")
CRON_SECRET_KEY = os.getenv("CRON_SECRET_KEY")


def get_db_connection():
    return get_conn()


def get_valid_access_token(athlete_id):
    tokens = get_tokens_pg(athlete_id)
    if not tokens:
        raise Exception(f"No tokens for athlete {athlete_id}")
    access, refresh = tokens["access_token"], tokens["refresh_token"]

    # Test current token; refresh if expired
    res = requests.get(
        "https://www.strava.com/api/v3/athlete",
        headers={"Authorization": f"Bearer {access}"}
    )
    if res.status_code == 401:
        logging.info("🔁 Token expired; refreshing for athlete %s", athlete_id)
        rr = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type":    "refresh_token",
                "refresh_token": refresh
            }
        )
        rr.raise_for_status()
        data = rr.json()
        access, refresh = data["access_token"], data["refresh_token"]
        save_token_pg(athlete_id, access, refresh)

    return access


def insert_activities(activities, athlete_id):
    conn = get_db_connection()
    cur = conn.cursor()
    is_sqlite = isinstance(conn, sqlite3.Connection)

    # If SQLite, ensure the table exists
    if is_sqlite:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
              activity_id INTEGER PRIMARY KEY,
              athlete_id INTEGER NOT NULL,
              name TEXT NOT NULL,
              start_date TEXT NOT NULL,
              distance_mi REAL NOT NULL,
              moving_time_min REAL NOT NULL,
              pace_min_per_mile REAL NOT NULL,
              data TEXT NOT NULL
            );
        """)

    for a in activities:
        start = a.get("start_date_local") or a.get("start_date")
        if not start:
            continue
        dist = a.get("distance", 0)
        mt = a.get("moving_time", 0)
        dmi = round(dist / 1609.34, 2) if dist else 0
        mtm = round(mt / 60, 2) if mt else 0
        pace = round(mtm / dmi, 2) if (dmi and mtm) else 0
        payload = (
            a["id"], athlete_id, a.get("name"), start,
            dmi, mtm, pace, json.dumps(a)
        )

        if is_sqlite:
            # SQLite uses ? placeholders and INSERT OR IGNORE
            cur.execute("""
                INSERT OR IGNORE INTO activities (
                  activity_id, athlete_id, name, start_date,
                  distance_mi, moving_time_min, pace_min_per_mile, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, payload)
        else:
            # Postgres/psycopg2 uses %s placeholders
            cur.execute("""
                INSERT INTO activities (
                  activity_id, athlete_id, name, start_date,
                  distance_mi, moving_time_min, pace_min_per_mile, data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (activity_id) DO NOTHING;
            """, payload)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return "🚂 Smoke test v2!"


@app.route("/init-db")
def init_db():
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS tokens (
          athlete_id BIGINT PRIMARY KEY,
          access_token TEXT NOT NULL,
          refresh_token TEXT NOT NULL,
          updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS activities (
          activity_id BIGINT PRIMARY KEY,
          athlete_id BIGINT NOT NULL,
          name TEXT NOT NULL,
          start_date TIMESTAMP NOT NULL,
          distance_mi REAL NOT NULL,
          moving_time_min REAL NOT NULL,
          pace_min_per_mile REAL NOT NULL,
          data JSONB NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS run_splits (
          activity_id BIGINT NOT NULL,
          segment_index INT NOT NULL,
          distance_m REAL NOT NULL,
          elapsed_time REAL NOT NULL,
          pace REAL NOT NULL,
          average_heartrate REAL,
          PRIMARY KEY(activity_id, segment_index),
          FOREIGN KEY(activity_id) REFERENCES activities(activity_id)
        );
        """
    ]
    conn = get_db_connection()
    cur  = conn.cursor()
    for q in ddl:
        cur.execute(q)
    conn.commit()
    conn.close()
    return jsonify(initialized=True)


@app.route("/download-splits/<int:athlete_id>/<int:activity_id>")
def download_splits(athlete_id, activity_id):
    try:
        token = get_valid_access_token(athlete_id)

        # fetch the streams
        r = requests.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}/streams",
            params={"keys": "distance,time,heartrate", "key_by_type": "true"},
            headers={"Authorization": f"Bearer {token}"}
        )
        r.raise_for_status()
        streams = r.json()

        dists = streams["distance"]["data"]
        times = streams["time"]["data"]
        hrs   = streams.get("heartrate", {}).get("data", [])

        splits = []
        mile_mark = 1609.34
        segment   = 1
        for i, dist in enumerate(dists):
            if dist >= mile_mark * segment:
                elapsed = times[i]
                pace    = elapsed / (dist / mile_mark)
                splits.append({
                    "segment_index":     segment,
                    "distance":          dist,
                    "elapsed_time":      elapsed,
                    "pace":              pace,
                    "average_heartrate": hrs[i] if i < len(hrs) else None
                })
                segment += 1

        save_run_splits(activity_id, splits)
        return jsonify(activity_id=activity_id, splits=len(splits))

    except Exception as e:
        logging.exception("❌ /download-splits failed")
        return jsonify(error=str(e)), 500


@app.route("/debug-env")
def debug_env():
    return jsonify(DATABASE_URL=os.getenv("DATABASE_URL"))


@app.route("/connect-strava")
def connect_strava():
    params = {
        "client_id":       CLIENT_ID,
        "redirect_uri":    REDIRECT_URI,
        "response_type":   "code",
        "approval_prompt": "force",
        "scope":           "activity:read_all,activity:read,activity:write"
    }
    url = f"https://www.strava.com/oauth/authorize?{requests.compat.urlencode(params)}"
    return redirect(url)


@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return jsonify(error="Missing code parameter"), 400

    r = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code":          code,
            "grant_type":    "authorization_code"
        }
    )
    if r.status_code != 200:
        return jsonify(error="Token exchange failed", details=r.text), 400

    data       = r.json()
    athlete_id = data["athlete"]["id"]
    save_token_pg(athlete_id, data["access_token"], data["refresh_token"])
    return jsonify(athlete_id=athlete_id, message="Strava tokens saved")


@app.route("/sync-strava-to-db/<int:athlete_id>")
def sync_strava_to_db(athlete_id):
    key = request.args.get("key")
    if CRON_SECRET_KEY and key != CRON_SECRET_KEY:
        return jsonify(error="Unauthorized"), 401

    token = get_valid_access_token(athlete_id)
    r     = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    insert_activities(r.json(), athlete_id)
    return jsonify(synced=len(r.json()))



@app.route("/activities/<int:athlete_id>")
def get_activities(athlete_id):
    conn = get_db_connection()
    is_sqlite = isinstance(conn, sqlite3.Connection)

    if is_sqlite:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT activity_id, name, start_date,
                   distance_mi, pace_min_per_mile
            FROM activities
            WHERE athlete_id = ?
            ORDER BY start_date DESC
            """,
            (athlete_id,)
        )
        # build list of dicts
        cols = [col[0] for col in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    else:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT activity_id, name, start_date,
                   distance_mi, pace_min_per_mile
            FROM activities
            WHERE athlete_id = %s
            ORDER BY start_date DESC
            """,
            (athlete_id,)
        )
        rows = cur.fetchall()

    conn.close()
    return jsonify(rows)



@app.route("/enrich-activities/<int:athlete_id>")
def enrich_activities(athlete_id):
    try:
        # Determine if we’re on SQLite (dev) or Postgres (prod)
        conn = get_db_connection()
        is_sqlite = isinstance(conn, sqlite3.Connection)
        cur = conn.cursor()

        # Fetch all activity IDs for this athlete
        if is_sqlite:
            cur.execute(
                "SELECT activity_id FROM activities WHERE athlete_id = ?",
                (athlete_id,)
            )
        else:
            cur.execute(
                "SELECT activity_id FROM activities WHERE athlete_id = %s",
                (athlete_id,)
            )
        ids = [row[0] for row in cur.fetchall()]
        conn.close()

        count = 0
        token = get_valid_access_token(athlete_id)

        MAX_RETRIES = 5
        RETRY_DELAY = 10  # seconds

        for aid in ids:
            for attempt in range(1, MAX_RETRIES + 1):
                rr = requests.get(
                    f"https://www.strava.com/api/v3/activities/{aid}?include_all_efforts=true",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if rr.status_code == 200:
                    enrich_activity_pg(aid, rr.json())
                    count += 1
                    break
                elif rr.status_code == 429:
                    wait = int(rr.headers.get("Retry-After", RETRY_DELAY))
                    app.logger.warning(
                        "Rate limit hit for %s (attempt %s/%s), sleeping %ss…",
                        aid, attempt, MAX_RETRIES, wait
                    )
                    time.sleep(wait)
                else:
                    rr.raise_for_status()
            else:
                app.logger.error(
                    "Failed to enrich %s after %s retries; skipping",
                    aid, MAX_RETRIES
                )

        return jsonify(enriched=count)

    except Exception as e:
        logging.exception("❌ /enrich-activities failed")
        tb = traceback.format_exc()
        return jsonify(error=str(e), traceback=tb), 500





@app.route("/metrics/<int:athlete_id>")
def get_metrics(athlete_id):
    conn = get_db_connection()
    is_sqlite = isinstance(conn, sqlite3.Connection)
    if is_sqlite:
        cur = conn.cursor()
        # Run SQLite-compatible query (store JSON as TEXT)
        cur.execute(
            """
            SELECT activity_id, name, start_date,
                   distance_mi, pace_min_per_mile,
                   json_extract(data, '$.average_heartrate') AS avg_hr,
                   json_extract(data, '$.max_heartrate')     AS max_hr,
                   json_extract(data, '$.average_cadence')    AS cadence,
                   json_extract(data, '$.total_elevation_gain') AS elevation
            FROM activities
            WHERE athlete_id = ?
            ORDER BY start_date DESC
            """, (athlete_id,)
        )
        rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
    else:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT activity_id, name, start_date,
                   distance_mi, pace_min_per_mile,
                   (data->>'average_heartrate')::FLOAT AS avg_hr,
                   (data->>'max_heartrate')::FLOAT     AS max_hr,
                   (data->>'average_cadence')::FLOAT    AS cadence,
                   (data->>'total_elevation_gain')::FLOAT AS elevation
            FROM activities
            WHERE athlete_id = %s
            ORDER BY start_date DESC
            """, (athlete_id,)
        )
        rows = cur.fetchall()
    conn.close()
    return jsonify(rows)



@app.route("/export/<int:athlete_id>")
def export_activities(athlete_id):
    fmt = request.args.get("format", "csv").lower()
    conn = get_db_connection()
    is_sqlite = isinstance(conn, sqlite3.Connection)

    # Retrieve data
    if is_sqlite:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT activity_id, name, start_date,
                   distance_mi,
                   pace_min_per_mile,
                   json_extract(data, '$.average_heartrate') AS avg_hr,
                   json_extract(data, '$.max_heartrate')     AS max_hr,
                   json_extract(data, '$.average_cadence')    AS cadence,
                   json_extract(data, '$.total_elevation_gain') AS elevation
            FROM activities
            WHERE athlete_id = ?
            ORDER BY start_date DESC
            """, (athlete_id,)
        )
        columns = [c[0] for c in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    else:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT activity_id, name, start_date,
                   distance_mi,
                   pace_min_per_mile,
                   (data->>'average_heartrate')::FLOAT AS avg_hr,
                   (data->>'max_heartrate')::FLOAT     AS max_hr,
                   (data->>'average_cadence')::FLOAT    AS cadence,
                   (data->>'total_elevation_gain')::FLOAT AS elevation
            FROM activities
            WHERE athlete_id = %s
            ORDER BY start_date DESC
            """, (athlete_id,)
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    conn.close()

    # Prepare buffer
    if fmt == "xlsx":
        df = pd.DataFrame(rows)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        name = "activities.xlsx"
    else:
        import io
        text_buf = io.StringIO()
        writer = csv.DictWriter(text_buf, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        buf = BytesIO(text_buf.getvalue().encode('utf-8'))
        mimetype = "text/csv"
        name = "activities.csv"

    return send_file(buf, as_attachment=True, download_name=name, mimetype=mimetype)

@app.route("/admin/drop-mile-splits", methods=["POST"])
def drop_mile_splits():
    # simple key check, same as sync endpoint
    key = request.args.get("key")
    if CRON_SECRET_KEY and key != CRON_SECRET_KEY:
        return jsonify(error="Unauthorized"), 401

    conn = get_db_connection()
    cur = conn.cursor()
    # Drop the unwanted table
    # For Postgres:
    cur.execute("DROP TABLE IF EXISTS public.mile_splits;")
    conn.commit()
    conn.close()
    return jsonify(dropped=True)


@app.route("/test-db")
def test_db():
    from flask import current_app
    try:
        conn = get_db_connection()       # calls your get_conn() under the hood
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        val = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify(db=val), 200
    except Exception as e:
        current_app.logger.exception("DB connectivity test failed")
        return jsonify(error=str(e)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))



