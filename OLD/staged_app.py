from flask import Flask, jsonify, redirect, request
import os, sys, json, requests, time
from db import get_conn, get_tokens_pg, save_token_pg
from src.app import get_valid_access_token
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

CLIENT_ID     = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("REDIRECT_URI") or "http://127.0.0.1:5000/oauth/callback"

# 🔁 New: Token refresh logic
def refresh_access_token(athlete_id, refresh_token):
    response = requests.post("https://www.strava.com/api/v3/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
    if response.status_code == 200:
        tokens = response.json()
        save_token_pg(athlete_id, tokens["access_token"], tokens["refresh_token"])
        print(f"✅ Token refreshed successfully for athlete {athlete_id}")
        return tokens["access_token"]
    else:
        print(f"❌ Refresh token failed for athlete {athlete_id}: {response.status_code} — {response.text}")
        return None

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

    resp = requests.post("https://www.strava.com/api/v3/oauth/token", data={
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

@app.route("/enrich-activities/<int:athlete_id>")
def enrich_activities(athlete_id):
    key = request.args.get("key")
    limit = int(request.args.get("limit", 10))
    offset = int(request.args.get("offset", 0))

    if os.getenv("CRON_SECRET_KEY") and key != os.getenv("CRON_SECRET_KEY"):
        return jsonify(error="Unauthorized"), 401

    tokens = get_tokens_pg(athlete_id)
    if not tokens:
        return jsonify(error="No tokens for that athlete"), 404
    token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT activity_id FROM activities
        WHERE enriched_failed = FALSE
          AND (enriched_successful IS NULL OR enriched_successful = FALSE)
        ORDER BY start_date DESC
        OFFSET %s LIMIT %s;
    """, (offset, limit))
    rows = cur.fetchall()

    enriched = 0
    for (activity_id,) in rows:
        resp = requests.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        if resp.status_code == 429:
            print("⏳ Rate limit hit. Sleeping for 10 minutes...")
            time.sleep(600)
            continue

        if resp.status_code == 401:
            print(f"🔁 Token expired for athlete {athlete_id}. Refreshing token...")
            token = refresh_access_token(athlete_id, refresh_token)
            if not token:
                print(f"❌ Failed to refresh token for {athlete_id}. Skipping...")
                cur.execute("UPDATE activities SET enriched_failed = TRUE WHERE activity_id = %s;", (activity_id,))
                continue
            resp = requests.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers={"Authorization": f"Bearer {token}"}
            )

        if resp.status_code != 200:
            print(f"⚠️ Failed to fetch details for {activity_id} — HTTP {resp.status_code}")
            cur.execute("UPDATE activities SET enriched_failed = TRUE WHERE activity_id = %s;", (activity_id,))
            continue

        a = resp.json()

        r_zones = requests.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}/zones",
            headers={"Authorization": f"Bearer {token}"}
        )
        zones_json = r_zones.json() if r_zones.status_code == 200 else []

        zone_times = {1: None, 2: None, 3: None, 4: None, 5: None}
        for zone_entry in zones_json:
            if zone_entry.get("type") == "heartrate":
                for z in zone_entry.get("zones", []):
                    zone_num = z.get("zone")
                    seconds = z.get("time")
                    if zone_num and seconds is not None:
                        zone_times[zone_num] = round(seconds / 60, 2)

        print(f"🔧 About to enrich and update activity {activity_id}")

        cur.execute("""
            UPDATE activities SET
                average_heartrate = %s,
                max_heartrate = %s,
                average_speed_mph = %s,
                max_speed_mph = %s,
                total_elevation_gain = %s,
                calories = %s,
                avg_cadence = %s,
                suffer_score = %s,
                data = %s,
                type = %s,
                enriched_failed = FALSE,
                enriched_successful = TRUE
            WHERE activity_id = %s;
        """, (
            a.get("average_heartrate"),
            a.get("max_heartrate"),
            round(a.get("average_speed", 0) * 2.23694, 2) if a.get("average_speed") else None,
            round(a.get("max_speed", 0) * 2.23694, 2) if a.get("max_speed") else None,
            a.get("total_elevation_gain"),
            a.get("calories"),
            a.get("average_cadence"),
            a.get("suffer_score"),
            json.dumps(a),
            a.get("type"),
            activity_id
        ))
        enriched += 1
        print(f"✅ Enriched and marked successful: {activity_id}")

        time.sleep(1.5)  # 🔁 pacing for safety

    conn.commit()
    conn.close()

    return jsonify(enriched=enriched, processed=len(rows), offset=offset), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
