import os, sys
print(f"\n▶️ Loading app.py from: {__file__!r}")
print(f"▶️ Current working dir: {os.getcwd()!r}\n", file=sys.stdout)




import json
import logging
import requests
from io import BytesIO

import pandas as pd
from flask import Flask, redirect, request, jsonify, send_file
from psycopg2.extras import RealDictCursor

from db import (
    get_conn,
    save_token_pg,
    get_tokens_pg,
    save_activity_pg,
    save_run_splits,      # ← add this helper to db.py
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

    # test & refresh if needed
    r = requests.get("https://www.strava.com/api/v3/athlete",
                     headers={"Authorization": f"Bearer {access}"})
    if r.status_code == 401:
        logging.info("Refreshing token for %s", athlete_id)
        rr = requests.post("https://www.strava.com/oauth/token", data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "refresh_token",
            "refresh_token": refresh
        })
        rr.raise_for_status()
        data = rr.json()
        access, refresh = data["access_token"], data["refresh_token"]
        save_token_pg(athlete_id, access, refresh)

    return access


def insert_activities(activities, athlete_id):
    conn = get_db_connection()
    cur  = conn.cursor()
    for a in activities:
        start = a.get("start_date_local") or a.get("start_date")
        if not start:
            continue
        dist = a.get("distance", 0)
        mt   = a.get("moving_time", 0)
        dmi  = round(dist/1609.34, 2) if dist else 0
        mtm  = round(mt/60, 2)       if mt   else 0
        pace = round(mtm/dmi, 2)     if (dmi and mtm) else 0

        cur.execute("""
            INSERT INTO activities (
              activity_id, athlete_id, name, start_date,
              distance_mi, moving_time_min, pace_min_per_mile, data
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, (
            a["id"], athlete_id, a["name"], start,
            dmi, mtm, pace, json.dumps(a)
        ))
    conn.commit()
    conn.close()


@app.route("/")
def home():
    return "🚂 Smoke test live"


@app.route("/init-db")
def init_db():
    sql = [
        """
        CREATE TABLE IF NOT EXISTS tokens (
          athlete_id BIGINT PRIMARY KEY,
          access_token TEXT,
          refresh_token TEXT,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS activities (
          activity_id BIGINT PRIMARY KEY,
          athlete_id BIGINT NOT NULL,
          name TEXT NOT NULL,
          start_date TIMESTAMP NOT NULL,
          distance_mi REAL,
          moving_time_min REAL,
          pace_min_per_mile REAL,
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
    for q in sql:
        cur.execute(q)
    conn.commit()
    conn.close()
    return jsonify(initialized=True)


@app.route("/download-splits/<int:athlete_id>/<int:activity_id>")
def download_splits(athlete_id, activity_id):
    token = get_valid_access_token(athlete_id)
    r = requests.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}/streams",
        params={"keys":"distance,time,heartrate","key_by_type":"true"},
        headers={"Authorization":f"Bearer {token}"}
    )
    r.raise_for_status()
    s = r.json()
    dists = s["distance"]["data"]
    times = s["time"]["data"]
    hrs   = s.get("heartrate",{}).get("data",[])
    splits=[]
    mile=1609.34; idx=1
    for i,dist in enumerate(dists):
        if dist>=mile*idx:
            elapsed=times[i]
            pace=elapsed/(dist/mile)
            splits.append({
                "segment_index":idx,
                "distance":dist,
                "elapsed_time":elapsed,
                "pace":pace,
                "average_heartrate":hrs[i] if i<len(hrs) else None
            })
            idx+=1
    save_run_splits(activity_id, splits)
    return jsonify(activity_id=activity_id, splits=len(splits))


@app.route("/debug-env")
def debug_env():
    return jsonify(DATABASE_URL=os.getenv("DATABASE_URL"))




@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return jsonify(error="Missing code"),400
    r = requests.post("https://www.strava.com/oauth/token", data={
        "client_id":CLIENT_ID,
        "client_secret":CLIENT_SECRET,
        "code":code,
        "grant_type":"authorization_code"
    })
    if r.status_code!=200:
        return jsonify(error="Token exchange failed", details=r.text),400

    t=r.json()
    aid=t["athlete"]["id"]
    save_token_pg(aid, t["access_token"], t["refresh_token"])
    return jsonify(athlete_id=aid, message="Tokens saved")


@app.route("/sync-strava-to-db/<int:athlete_id>")
def sync_strava_to_db(athlete_id):
    key=request.args.get("key")
    if CRON_SECRET_KEY and key!=CRON_SECRET_KEY:
        return jsonify(error="Unauthorized"),401
    token=get_valid_access_token(athlete_id)
    r=requests.get(
      "https://www.strava.com/api/v3/athlete/activities",
      headers={"Authorization":f"Bearer {token}"}
    )
    r.raise_for_status()
    insert_activities(r.json(), athlete_id)
    return jsonify(synced=len(r.json()))


@app.route("/activities/<int:athlete_id>")
def get_activities(athlete_id):
    conn=get_db_connection()
    cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
      SELECT activity_id,name,start_date,distance_mi,pace_min_per_mile
      FROM activities
      WHERE athlete_id=%s
      ORDER BY start_date DESC
    """,(athlete_id,))
    res=cur.fetchall()
    conn.close()
    return jsonify(res)


@app.route("/enrich-activities/<int:athlete_id>")
def enrich_activities(athlete_id):
    token=get_valid_access_token(athlete_id)
    conn=get_db_connection()
    cur=conn.cursor()
    cur.execute("SELECT activity_id FROM activities WHERE athlete_id=%s",(athlete_id,))
    ids=[r[0] for r in cur.fetchall()]
    conn.close()
    count=0
    for aid in ids:
        rr=requests.get(
          f"https://www.strava.com/api/v3/activities/{aid}?include_all_efforts=true",
          headers={"Authorization":f"Bearer {token}"}
        )
        if rr.status_code==200:
            enrich_activity_pg(aid, rr.json())
            count+=1
    return jsonify(enriched=count)


@app.route("/metrics/<int:athlete_id>")
def get_metrics(athlete_id):
    conn=get_db_connection()
    cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
      SELECT activity_id,name,start_date,
             distance_mi,pace_min_per_mile,
             (data->>'average_heartrate')::float avg_hr,
             (data->>'max_heartrate')::float     max_hr,
             (data->>'average_cadence')::float    cadence,
             (data->>'total_elevation_gain')::float elevation
      FROM activities
      WHERE athlete_id=%s
      ORDER BY start_date DESC
    """,(athlete_id,))
    res=cur.fetchall()
    conn.close()
    return jsonify(res)


@app.route("/export/<int:athlete_id>")
def export_activities(athlete_id):
    fmt=request.args.get("format","csv")
    conn=get_db_connection()
    cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
      SELECT activity_id,name,start_date,
             distance_mi,pace_min_per_mile,
             (data->>'average_heartrate')::float avg_hr,
             (data->>'max_heartrate')::float     max_hr,
             (data->>'average_cadence')::float    cadence,
             (data->>'total_elevation_gain')::float elevation
      FROM activities WHERE athlete_id=%s
      ORDER BY start_date DESC
    """,(athlete_id,))
    df=pd.DataFrame(cur.fetchall())
    conn.close()

    buf=BytesIO()
    if fmt=="xlsx":
        with pd.ExcelWriter(buf,engine="openpyxl") as w: df.to_excel(w,index=False)
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        fn="activities.xlsx"
    else:
        df.to_csv(buf,index=False)
        mime="text/csv"; fn="activities.csv"
    buf.seek(0)
    return send_file(buf,as_attachment=True,download_name=fn,mimetype=mime)


@app.route("/cron-status/<int:athlete_id>")
def cron_status(athlete_id):
    conn=get_db_connection()
    cur=conn.cursor()
    cur.execute("SELECT MAX(start_date) FROM activities WHERE athlete_id=%s",(athlete_id,))
    last_synced=cur.fetchone()[0]
    cur.execute("""
      SELECT MAX(start_date) FROM activities
      WHERE athlete_id=%s AND (data->>'average_heartrate') IS NOT NULL
    """,(athlete_id,))
    last_enriched=cur.fetchone()[0]
    conn.close()
    return jsonify(
      last_synced=last_synced.isoformat() if last_synced else None,
      last_enriched=last_enriched.isoformat() if last_enriched else None
    )


@app.route("/connect-strava")
def connect_strava():
    print("🔥 connect_strava() ENTERED")      # ← add this
    app.logger.info("▶️  connect_strava() invoked")
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": "activity:read,activity:write"
    }
    url = f"https://www.strava.com/oauth/authorize?{requests.compat.urlencode(params)}"
    return redirect(url)


@app.route("/test-connect")
def test_connect():
    print("🧪 test_connect() invoked")
    return "Test endpoint OK", 200

# ─── DEBUG: list all registered routes ───
import sys
print("\nRegistered routes:")
for rule in app.url_map.iter_rules():
    print(f" • {rule.rule}")
print("────────────────────\n", file=sys.stdout)



if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
