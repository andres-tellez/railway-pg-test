import os
import time
import json
import requests
from db import get_conn, get_tokens_pg, save_token_pg
from services.token_manager import refresh_access_token

API_BASE         = "https://www.strava.com/api/v3"
RATE_LIMIT_SLEEP = 600  # 10 minutes
PACING_SLEEP     = 1.5

def enrich_batch(athlete_id, key, limit, offset, client_id, client_secret):
    """
    Process one batch of activities exactly as staged_app.py did:
      - on 429: sleep & continue
      - on 401: refresh token & retry
      - on other errors: mark failed & continue
      - after loop: commit & return
    """
    # Authorization check
    if os.getenv("CRON_SECRET_KEY") and key != os.getenv("CRON_SECRET_KEY"):
        raise PermissionError("Unauthorized key")

    conn = get_conn()
    cur  = conn.cursor()

    # Fetch pending IDs
    cur.execute("""
        SELECT activity_id
        FROM activities
        WHERE enriched_failed = FALSE
          AND (enriched_successful IS NULL OR enriched_successful = FALSE)
        ORDER BY start_date DESC
        OFFSET %s LIMIT %s;
    """, (offset, limit))
    rows = cur.fetchall()

    enriched_count = 0
    for (activity_id,) in rows:
        # 1) GET activity
        resp = requests.get(
            f"{API_BASE}/activities/{activity_id}",
            headers={"Authorization": f"Bearer {get_tokens_pg(athlete_id)['access_token']}"}
        )

        # Rate limit: sleep & skip to next activity
        if resp.status_code == 429:
            print("⏳ Rate limit hit. Sleeping for 10 minutes...")
            time.sleep(RATE_LIMIT_SLEEP)
            continue

        # Unauthorized: refresh token & retry once
        if resp.status_code == 401:
            print(f"🔁 Token expired. Refreshing for athlete {athlete_id}...")
            tokens = get_tokens_pg(athlete_id)
            new_token = refresh_access_token(athlete_id, tokens["refresh_token"], client_id, client_secret)
            if not new_token:
                print(f"❌ Refresh failed for {athlete_id}. Marking FAIL.")
                cur.execute("UPDATE activities SET enriched_failed = TRUE WHERE activity_id = %s;", (activity_id,))
                continue
            resp = requests.get(
                f"{API_BASE}/activities/{activity_id}",
                headers={"Authorization": f"Bearer {new_token}"}
            )

        # Any other non‐200 is a failure
        if resp.status_code != 200:
            print(f"⚠️ Failed to fetch {activity_id}: HTTP {resp.status_code}. Marking FAIL.")
            cur.execute("UPDATE activities SET enriched_failed = TRUE WHERE activity_id = %s;", (activity_id,))
            continue

        # Successful fetch: parse JSON
        a = resp.json()

        # 2) GET zones
        r_zones = requests.get(
            f"{API_BASE}/activities/{activity_id}/zones",
            headers={"Authorization": f"Bearer {get_tokens_pg(athlete_id)['access_token']}"}
        )
        zones_json = r_zones.json() if r_zones.status_code == 200 else []
        zone_times = {i: None for i in range(1, 6)}
        for ze in zones_json:
            if ze.get("type") == "heartrate":
                for z in ze.get("zones", []):
                    zn, tm = z.get("zone"), z.get("time")
                    if zn and tm is not None:
                        zone_times[zn] = round(tm / 60, 2)

        # 3) UPDATE activity record
        print(f"🔧 Enriching activity {activity_id}")
        cur.execute("""
            UPDATE activities SET
                average_heartrate    = %s,
                max_heartrate        = %s,
                average_speed_mph    = %s,
                max_speed_mph        = %s,
                total_elevation_gain = %s,
                calories             = %s,
                avg_cadence          = %s,
                suffer_score         = %s,
                data                 = %s,
                type                 = %s,
                enriched_failed      = FALSE,
                enriched_successful  = TRUE
            WHERE activity_id = %s;
        """, (
            a.get("average_heartrate"),
            a.get("max_heartrate"),
            round(a.get("average_speed", 0) * 2.23694, 2) if a.get("average_speed") else None,
            round(a.get("max_speed", 0) * 2.23694, 2)     if a.get("max_speed")     else None,
            a.get("total_elevation_gain"),
            a.get("calories"),
            a.get("average_cadence"),
            a.get("suffer_score"),
            json.dumps(a),
            a.get("type"),
            activity_id
        ))
        enriched_count += 1
        print(f"✅ Enriched and marked successful: {activity_id}")

        # Pace between calls
        time.sleep(PACING_SLEEP)

    # 4) Commit & cleanup
    conn.commit()
    conn.close()

    # offset unchanged so next run picks up correctly
    return enriched_count, len(rows), offset
