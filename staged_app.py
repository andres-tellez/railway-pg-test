# staged_app.py

import os
import sys
import json
import requests

from flask import Flask, jsonify, redirect, request
from db import (
    get_conn,
    get_tokens_pg,
    save_activity_pg,
    save_token_pg,
    enrich_activity_pg
)
from app import get_valid_access_token

app = Flask(__name__)

CLIENT_ID     = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("REDIRECT_URI") or "http://127.0.0.1:5000/oauth/callback"

@app.route("/")
def home():
    return "🚂 Smoke test live", 200

@app.route("/connect-strava")
def connect_strava():
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": "activity:read,activity:write"
    }
    url = f"https://www.strava.com/oauth/authorize?{requests.compat.urlencode(params)}"
    return redirect(url)

@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return jsonify(error="Missing code"), 400

    resp = requests.post("https://www.strava.com/oauth/token", data={
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code"
    })
    if resp.status_code != 200:
        return jsonify(error="Token exchange failed", details=resp.text), resp.status_code

    data = resp.json()
    athlete_id    = data["athlete"]["id"]
    access_token  = data["access_token"]
    refresh_token = data["refresh_token"]

    save_token_pg(athlete_id, access_token, refresh_token)

    return jsonify(
        athlete_id    = athlete_id,
        access_token  = access_token,
        refresh_token = refresh_token
    ), 200

@app.route("/sync-strava-to-db/<int:athlete_id>")
def sync_strava_to_db(athlete_id):
    key = request.args.get("key")
    if os.getenv("CRON_SECRET_KEY") and key != os.getenv("CRON_SECRET_KEY"):
        return jsonify(error="Unauthorized"), 401

    token = get_valid_access_token(athlete_id)
    resp = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    activities = resp.json()

    conn = get_conn()
    cur  = conn.cursor()
    for a in activities:
        dist_mi = round(a.get("distance", 0) / 1609.34, 2) if a.get("distance") else 0
        mov_min = round(a.get("moving_time", 0) / 60, 2)     if a.get("moving_time") else 0
        pace    = round(mov_min / dist_mi, 2)                 if (dist_mi and mov_min) else 0

        cur.execute("""
          INSERT INTO activities (
            activity_id,
            athlete_id,
            name,
            start_date,
            distance_mi,
            moving_time_min,
            pace_min_per_mile,
            data
          ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT DO NOTHING
        """, (
          a["id"],
          athlete_id,
          a.get("name"),
          a.get("start_date_local") or a.get("start_date"),
          dist_mi,
          mov_min,
          pace,
          json.dumps(a)
        ))
    conn.commit()
    conn.close()

    return jsonify(synced=len(activities)), 200

@app.route("/enrich-activities/<int:athlete_id>")
def enrich_activities(athlete_id):
    key = request.args.get("key")
    if os.getenv("CRON_SECRET_KEY") and key != os.getenv("CRON_SECRET_KEY"):
        return jsonify(error="Unauthorized"), 401

    token = get_valid_access_token(athlete_id)

    # fetch up to 10 IDs still lacking heart-rate
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
      SELECT activity_id
        FROM activities
       WHERE athlete_id = %s
         AND (data->>'average_heartrate') IS NULL
       LIMIT 10
    """, (athlete_id,))
    ids = [row[0] for row in cur.fetchall()]
    conn.close()

    count = 0
    for aid in ids:
        r = requests.get(
            f"https://www.strava.com/api/v3/activities/{aid}?include_all_efforts=true",
            headers={"Authorization": f"Bearer {token}"}
        )
        if r.status_code == 200:
            enrich_activity_pg(aid, r.json())
            count += 1

    return jsonify(enriched=count), 200

# ─── DEBUG: list routes on startup ───
print("\nRegistered routes:")
for rule in app.url_map.iter_rules():
    print(f" • {rule.rule}")
print("---------------------\n", file=sys.stdout)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
