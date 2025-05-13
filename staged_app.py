


from flask import Flask, jsonify, redirect, request
import os, sys, json, requests, time
from db import get_conn, get_tokens_pg, save_token_pg
from app import get_valid_access_token
from dotenv import load_dotenv

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

@app.route("/sync-strava-to-db/<int:athlete_id>")
def sync_strava_to_db(athlete_id):
    key = request.args.get("key")
    if os.getenv("CRON_SECRET_KEY") and key != os.getenv("CRON_SECRET_KEY"):
        return jsonify(error="Unauthorized"), 401

    tokens = get_tokens_pg(athlete_id)
    if not tokens:
        return jsonify(error="No tokens for that athlete"), 404
    token = tokens["access_token"]

    resp = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    activities = resp.json()

    conn = get_conn()
    cur  = conn.cursor()
    for a in activities:
        cur.execute("""
          INSERT INTO activities (
            activity_id, athlete_id, name, start_date,
            distance_mi, moving_time_min, average_speed_min_per_mile, data
          ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT DO NOTHING
        """, (
          a["id"], athlete_id, a["name"], a.get("start_date_local") or a.get("start_date"),
          round(a.get("distance", 0)/1609.34, 2),
          round(a.get("moving_time", 0)/60, 2),
          round((a.get("moving_time", 0)/60)/(a.get("distance", 1)/1609.34), 2) if a.get("distance") else None,
          json.dumps(a)
        ))
    conn.commit()
    conn.close()

    return jsonify(synced=len(activities)), 200


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

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT activity_id FROM activities
        WHERE enriched_failed = FALSE
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
                enriched_failed = FALSE
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

    conn.commit()
    conn.close()

    return jsonify(enriched=enriched, processed=len(rows), offset=offset), 200




@app.route("/enrich-latest-runs/<int:athlete_id>")
def enrich_latest_runs(athlete_id):
    key = request.args.get("key")
    if os.getenv("CRON_SECRET_KEY") and key != os.getenv("CRON_SECRET_KEY"):
        return jsonify(error="Unauthorized"), 401

    tokens = get_tokens_pg(athlete_id)
    if not tokens:
        return jsonify(error="No tokens for that athlete"), 404
    token = tokens["access_token"]

    resp = requests.get(
        "https://www.strava.com/api/v3/athlete/activities?per_page=50",
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code != 200:
        return jsonify(error="Failed to fetch activities", status=resp.status_code), resp.status_code

    runs = [a for a in resp.json() if a.get("type") == "Run"][:10]

    conn = get_conn()
    cur = conn.cursor()
    synced = enriched = 0

    for a in runs:
        activity_id = a["id"]

        cur.execute("""
            INSERT INTO activities (
              activity_id, athlete_id, name, start_date,
              distance_mi, moving_time_min, average_speed_min_per_mile, data
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, (
            activity_id, athlete_id, a["name"], a.get("start_date_local"),
            round(a.get("distance", 0) / 1609.34, 2),
            round(a.get("moving_time", 0) / 60, 2),
            round((a.get("moving_time", 0) / 60) / (a.get("distance", 1) / 1609.34), 2)
                if a.get("distance") else None,
            json.dumps(a)
        ))
        synced += 1

        detail_resp = requests.get(f"https://www.strava.com/api/v3/activities/{activity_id}", headers={"Authorization": f"Bearer {token}"})
        if detail_resp.status_code != 200:
            continue
        detailed = detail_resp.json()

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
                type = %s
            WHERE activity_id = %s;
        """, (
            detailed.get("average_heartrate"),
            detailed.get("max_heartrate"),
            round(detailed.get("average_speed", 0) * 2.23694, 2) if detailed.get("average_speed") else None,
            round(detailed.get("max_speed", 0) * 2.23694, 2) if detailed.get("max_speed") else None,
            detailed.get("total_elevation_gain"),
            detailed.get("calories"),
            detailed.get("average_cadence"),
            detailed.get("suffer_score"),
            json.dumps(detailed),
            detailed.get("type"),
            activity_id
        ))
        enriched += 1

    conn.commit()
    conn.close()

    return jsonify(synced=synced, enriched=enriched), 200

# ─── DEBUG ───
print("\nRegistered routes:")
for rule in app.url_map.iter_rules():
    print(f" • {rule.rule}")
print("---------------------\n", file=sys.stdout)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)