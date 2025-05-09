import os
import json
import logging
import requests
from datetime import datetime
from io import BytesIO

import pandas as pd
import psycopg2
from flask import Flask, redirect, request, jsonify, send_file
from psycopg2.extras import RealDictCursor

from db import (
    get_conn,
    save_token_pg,
    get_tokens_pg,
    enrich_activity_pg,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Strava credentials and callback
CLIENT_ID       = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET   = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI    = os.getenv("REDIRECT_URI")
CRON_SECRET_KEY = os.getenv("CRON_SECRET_KEY")


def get_db_connection():
    """Alias to get_conn for compatibility."""
    return get_conn()


def get_valid_access_token(athlete_id):
    """
    Retrieve stored tokens, refresh access token if expired, and return valid token.
    """
    tokens = get_tokens_pg(athlete_id)
    if not tokens:
        raise Exception(f"No tokens found for athlete {athlete_id}")

    access_token  = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Test token
    res = requests.get(
        "https://www.strava.com/api/v3/athlete",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if res.status_code == 401:
        logging.info(f"🔁 Token expired; refreshing for athlete {athlete_id}")
        refresh_res = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token
            }
        )
        refresh_res.raise_for_status()
        new_data = refresh_res.json()
        access_token  = new_data["access_token"]
        refresh_token = new_data["refresh_token"]
        save_token_pg(athlete_id, access_token, refresh_token)

    return access_token


def insert_activities(activities, athlete_id):
    """
    Bulk-insert Strava activities into Postgres, skipping duplicates.
    Handles both summary and detailed payloads gracefully.
    """
    conn = get_db_connection()
    with conn.cursor() as cur:
        for act in activities:
            # pick the correct date field
            start_date = act.get("start_date_local") or act.get("start_date")
            if not start_date:
                logging.warning(f"Skipping activity with no date: {act.get('id')}")
                continue

            distance_m = act.get("distance", 0)
            moving_s   = act.get("moving_time", 0)

            # compute metrics safely
            distance_mi     = round(distance_m / 1609.34, 2) if distance_m else 0
            moving_time_min = round(moving_s   / 60,     2) if moving_s   else 0
            pace = (round(moving_time_min / distance_mi, 2)
                    if moving_time_min and distance_mi else 0)

            cur.execute(
                """
                INSERT INTO activities (
                  activity_id, athlete_id, name, start_date,
                  distance_mi, moving_time_min, pace_min_per_mile, data
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (activity_id) DO NOTHING;
                """,
                (
                    act.get("id"),
                    athlete_id,
                    act.get("name"),
                    start_date,
                    distance_mi,
                    moving_time_min,
                    pace,
                    json.dumps(act),
                )
            )
        conn.commit()
    conn.close()


# ─── Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return "🚂 Railway smoke test is live!"


@app.route("/init-db")
def init_db():
    """
    Create the tokens and activities tables if they don't exist.
    """
    ddl_tokens = """
    CREATE TABLE IF NOT EXISTS tokens (
      athlete_id   BIGINT PRIMARY KEY,
      access_token TEXT NOT NULL,
      refresh_token TEXT NOT NULL,
      updated_at   TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    ddl_activities = """
    CREATE TABLE IF NOT EXISTS activities (
      activity_id        BIGINT      PRIMARY KEY,
      athlete_id         BIGINT      NOT NULL,
      name               TEXT        NOT NULL,
      start_date         TIMESTAMP   NOT NULL,
      distance_mi        REAL        NOT NULL,
      moving_time_min    REAL        NOT NULL,
      pace_min_per_mile  REAL        NOT NULL,
      data               JSONB       NOT NULL
    );
    """
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(ddl_tokens)
        cur.execute(ddl_activities)
    conn.commit()
    conn.close()
    return jsonify({"initialized": True})


@app.route("/debug-env")
def debug_env():
    return jsonify({"DATABASE_URL": os.getenv("DATABASE_URL")})


@app.route("/connect-strava")
def connect_strava():
    """
    Redirect the user to Strava's OAuth consent page.
    """
    params = {
        "client_id":       CLIENT_ID,
        "redirect_uri":    REDIRECT_URI,
        "response_type":   "code",
        "approval_prompt": "force",
        "scope":           "activity:read,activity:write"
    }
    url = f"https://www.strava.com/oauth/authorize?{requests.compat.urlencode(params)}"
    return redirect(url)


@app.route("/oauth/callback")
def oauth_callback():
    """
    Handle Strava redirect, exchange code for tokens, then save.
    """
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing code parameter"}), 400

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
        return jsonify({"error": "Token exchange failed", "details": r.text}), 400

    tdata        = r.json()
    athlete_id   = tdata["athlete"]["id"]
    access_token = tdata["access_token"]
    refresh_token= tdata["refresh_token"]
    save_token_pg(athlete_id, access_token, refresh_token)

    return jsonify({
        "athlete_id": athlete_id,
        "message":    "Strava tokens saved to DB"
    })


@app.route("/get-latest-run/<int:athlete_id>")
def get_latest_run(athlete_id):
    token = get_valid_access_token(athlete_id)
    r     = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {token}"},
        params={"per_page": 1}
    )
    r.raise_for_status()
    a = r.json()[0]
    return jsonify({
        "name":               a["name"],
        "distance_miles":     round(a["distance"]/1609.34, 2),
        "moving_time_min":    round(a["moving_time"]/60, 2),
        "pace_min_per_mile":  round((a["moving_time"]/60)/(a["distance"]/1609.34), 2),
        "date":               a["start_date_local"]
    })


@app.route("/sync-strava-to-db/<int:athlete_id>")
def sync_strava_to_db(athlete_id):
    # Optionally require a cron key
    key = request.args.get("key")
    if CRON_SECRET_KEY and key != CRON_SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    token = get_valid_access_token(athlete_id)
    r = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    insert_activities(r.json(), athlete_id)
    return jsonify({"synced": len(r.json())})


@app.route("/activities/<int:athlete_id>")
def get_activities(athlete_id):
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT activity_id, name, start_date,
                   distance_mi, pace_min_per_mile
            FROM activities
            WHERE athlete_id = %s
            ORDER BY start_date DESC
        """, (athlete_id,))
        results = cur.fetchall()
    conn.close()
    return jsonify(results)


@app.route("/enrich-activities/<int:athlete_id>")
def enrich_activities(athlete_id):
    token = get_valid_access_token(athlete_id)
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT activity_id FROM activities WHERE athlete_id=%s", (athlete_id,))
        ids = [r[0] for r in cur.fetchall()]
    conn.close()

    count = 0
    for aid in ids:
        rr = requests.get(
            f"https://www.strava.com/api/v3/activities/{aid}?include_all_efforts=true",
            headers={"Authorization": f"Bearer {token}"}
        )
        if rr.status_code == 200:
            enrich_activity_pg(aid, rr.json())
            count += 1

    return jsonify({"enriched": count})


@app.route("/metrics/<int:athlete_id>")
def get_metrics(athlete_id):
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
              activity_id, name, start_date,
              distance_mi, pace_min_per_mile,
              (data->>'average_heartrate')::FLOAT AS avg_hr,
              (data->>'max_heartrate')::FLOAT     AS max_hr,
              (data->>'average_cadence')::FLOAT    AS cadence,
              (data->>'total_elevation_gain')::FLOAT AS elevation
            FROM activities
            WHERE athlete_id = %s
            ORDER BY start_date DESC
        """, (athlete_id,))
        results = cur.fetchall()
    conn.close()
    return jsonify(results)


@app.route("/export/<int:athlete_id>")
def export_activities(athlete_id):
    fmt = request.args.get("format", "csv")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
              activity_id, name, start_date,
              distance_mi, pace_min_per_mile,
              (data->>'average_heartrate')::FLOAT AS avg_hr,
              (data->>'max_heartrate')::FLOAT     AS max_hr,
              (data->>'average_cadence')::FLOAT    AS cadence,
              (data->>'total_elevation_gain')::FLOAT AS elevation
            FROM activities
            WHERE athlete_id=%s
            ORDER BY start_date DESC
        """, (athlete_id,))
        df = pd.DataFrame(cur.fetchall())
    conn.close()

    buf = BytesIO()
    if fmt == "xlsx":
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "activities.xlsx"
    else:
        df.to_csv(buf, index=False)
        mimetype = "text/csv"
        filename = "activities.csv"

    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=filename, mimetype=mimetype)


@app.route("/cron-status/<int:athlete_id>")
def cron_status(athlete_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(start_date) FROM activities WHERE athlete_id = %s", (athlete_id,))
        last_synced = cur.fetchone()[0]
        cur.execute("""
            SELECT MAX(start_date)
            FROM activities
            WHERE athlete_id = %s AND (data->>'average_heartrate') IS NOT NULL
        """, (athlete_id,))
        last_enriched = cur.fetchone()[0]
    conn.close()

    return jsonify({
        "last_synced":   last_synced.isoformat()   if last_synced   else None,
        "last_enriched": last_enriched.isoformat() if last_enriched else None
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
