# app.py

import os
import io
import json
import logging
import time
import requests
import sqlite3

from io import BytesIO
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


def get_valid_access_token(athlete_id: int) -> str:
    tokens = get_tokens_pg(athlete_id)
    if not tokens:
        raise RuntimeError(f"No tokens for athlete {athlete_id}")

    access, refresh = tokens["access_token"], tokens["refresh_token"]
    resp = requests.get(
        "https://www.strava.com/api/v3/athlete",
        headers={"Authorization": f"Bearer {access}"}
    )

    if resp.status_code == 401:
        logging.info("🔁 Refreshing token for athlete %s", athlete_id)
        refresh_resp = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type":    "refresh_token",
                "refresh_token": refresh
            }
        )
        refresh_resp.raise_for_status()
        data = refresh_resp.json()
        access, refresh = data["access_token"], data["refresh_token"]
        save_token_pg(athlete_id, access, refresh)

    return access


@app.route("/")
def home():
    return "🚂 Smoke test v2!"


@app.route("/init-db")
def init_db():
    """Create tokens, activities & run_splits tables in Postgres (no-ops if they exist)."""
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS tokens (
          athlete_id   BIGINT PRIMARY KEY,
          access_token TEXT NOT NULL,
          refresh_token TEXT NOT NULL,
          updated_at   TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );""",
        """
        CREATE TABLE IF NOT EXISTS activities (
          activity_id        BIGINT PRIMARY KEY,
          athlete_id         BIGINT NOT NULL,
          name               TEXT        NOT NULL,
          start_date         TIMESTAMP   NOT NULL,
          distance_mi        REAL        NOT NULL,
          moving_time_min    REAL        NOT NULL,
          pace_min_per_mile  REAL        NOT NULL,
          data               JSONB       NOT NULL
        );""",
        """
        CREATE TABLE IF NOT EXISTS run_splits (
          activity_id       BIGINT,
          segment_index     INTEGER,
          distance_m        REAL,
          elapsed_time      REAL,
          pace              REAL,
          average_heartrate REAL,
          PRIMARY KEY(activity_id, segment_index)
        );"""
    ]

    conn = get_conn()
    with conn.cursor() as cur:
        for sql in ddl:
            cur.execute(sql)
    conn.commit()
    conn.close()

    return jsonify(initialized=True)


@app.route("/test-connect")
def test_connect():
    return "Test endpoint OK", 200


@app.route("/connect-strava")
def connect_strava():
    params = {
        "client_id":       CLIENT_ID,
        "redirect_uri":    REDIRECT_URI,
        "response_type":   "code",
        "approval_prompt": "force",
        "scope":           "activity:read,activity:write"
    }
    url = "https://www.strava.com/oauth/authorize?" + requests.compat.urlencode(params)
    return redirect(url)


@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return jsonify(error="Missing code"), 400

    token_resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code":          code,
            "grant_type":    "authorization_code"
        }
    )
    if token_resp.status_code != 200:
        return jsonify(error="Token exchange failed", details=token_resp.text), 400

    t   = token_resp.json()
    aid = t["athlete"]["id"]
    save_token_pg(aid, t["access_token"], t["refresh_token"])
    return jsonify(athlete_id=aid, message="Tokens saved")


@app.route("/sync-strava-to-db/<int:athlete_id>")
def sync_strava_to_db(athlete_id):
    key = request.args.get("key")
    if CRON_SECRET_KEY and key != CRON_SECRET_KEY:
        return jsonify(error="Unauthorized"), 401

    token = get_valid_access_token(athlete_id)
    act_resp = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {token}"}
    )
    act_resp.raise_for_status()

    # reuse common saver
    for activity in act_resp.json():
        save_activity_pg(activity)

    return jsonify(synced=len(act_resp.json()))


@app.route("/activities/<int:athlete_id>")
def list_activities(athlete_id):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT activity_id, name, start_date, distance_mi, pace_min_per_mile
          FROM activities
         WHERE athlete_id = %s
         ORDER BY start_date DESC
    """, (athlete_id,))
    rows = cur.fetchall()
    conn.close()
    return jsonify(rows)


@app.route("/download-splits/<int:athlete_id>/<int:activity_id>")
def download_splits(athlete_id, activity_id):
    try:
        token = get_valid_access_token(athlete_id)
        streams = requests.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}/streams",
            params={"keys":"distance,time,heartrate","key_by_type":"true"},
            headers={"Authorization": f"Bearer {token}"}
        ).json()

        dists  = streams["distance"]["data"]
        times  = streams["time"]["data"]
        hrs    = streams.get("heartrate",{}).get("data",[])
        splits = []
        mile   = 1609.34
        segment = 1

        for i, dist in enumerate(dists):
            if dist >= mile * segment:
                elapsed = times[i]
                splits.append({
                    "segment_index":     segment,
                    "distance":          dist,
                    "elapsed_time":      elapsed,
                    "pace":              elapsed / (dist / mile),
                    "average_heartrate": hrs[i] if i < len(hrs) else None
                })
                segment += 1

        save_run_splits(activity_id, splits)
        return jsonify(activity_id=activity_id, splits=len(splits))

    except Exception as e:
        logging.exception("❌ download-splits error")
        return jsonify(error=str(e)), 500


@app.route("/enrich-activities/<int:athlete_id>")
def enrich_activities(athlete_id):
    limit  = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT activity_id
          FROM activities
         WHERE athlete_id = %s
         ORDER BY activity_id
         LIMIT %s OFFSET %s
    """, (athlete_id, limit, offset))

    ids = [row[0] for row in cur.fetchall()]
    conn.close()

    token = get_valid_access_token(athlete_id)
    count = 0

    for aid in ids:
        time.sleep(1.5)
        for retry in range(3):
            resp = requests.get(
                f"https://www.strava.com/api/v3/activities/{aid}?include_all_efforts=true",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 429:
                time.sleep(5 * (retry + 1))
                continue
            resp.raise_for_status()
            enrich_activity_pg(aid, resp.json())
            count += 1
            break

    return jsonify(enriched=count, limit=limit, offset=offset)


@app.route("/metrics/<int:athlete_id>")
def get_metrics(athlete_id):
    conn      = get_conn()
    is_sqlite = isinstance(conn, sqlite3.Connection)

    if is_sqlite:
        cur = conn.cursor()
        cur.execute("""
            SELECT
              activity_id, name, start_date, distance_mi, pace_min_per_mile,
              json_extract(data, '$.average_heartrate') AS avg_hr,
              json_extract(data, '$.max_heartrate')     AS max_hr,
              json_extract(data, '$.average_cadence')    AS cadence,
              json_extract(data, '$.total_elevation_gain') AS elevation
            FROM activities
           WHERE athlete_id = ?
           ORDER BY start_date DESC
        """, (athlete_id,))
        rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]

    else:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
              activity_id, name, start_date, distance_mi, pace_min_per_mile,
              (data->>'average_heartrate')::FLOAT AS avg_hr,
              (data->>'max_heartrate')::FLOAT     AS max_hr,
              (data->>'average_cadence')::FLOAT    AS cadence,
              (data->>'total_elevation_gain')::FLOAT AS elevation
            FROM activities
           WHERE athlete_id = %s
           ORDER BY start_date DESC
        """, (athlete_id,))
        rows = cur.fetchall()

    conn.close()
    return jsonify(rows)


@app.route("/export/<int:athlete_id>")
def export_activities(athlete_id):
    fmt  = request.args.get("format", "csv").lower()
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
          activity_id, name, start_date, distance_mi, pace_min_per_mile,
          (data->>'average_heartrate')::FLOAT AS avg_hr,
          (data->>'max_heartrate')::FLOAT     AS max_hr,
          (data->>'average_cadence')::FLOAT    AS cadence,
          (data->>'total_elevation_gain')::FLOAT AS elevation
        FROM activities
       WHERE athlete_id = %s
       ORDER BY start_date DESC
    """, (athlete_id,))
    rows = cur.fetchall()
    conn.close()

    if fmt == "xlsx":
        df = pd.DataFrame(rows)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)
        return send_file(buf,
                         as_attachment=True,
                         download_name="activities.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # default to CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys() if rows else [])
    writer.writeheader()
    writer.writerows(rows)
    buf = BytesIO(output.getvalue().encode("utf-8"))

    return send_file(buf, as_attachment=True, download_name="activities.csv", mimetype="text/csv")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
