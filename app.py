import os
import logging
from flask import Flask, jsonify
from psycopg2.extras import RealDictCursor

from db import (
    get_conn,
    save_token_pg,
    get_tokens_pg,
    save_activity_pg,
    enrich_activity_pg,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

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
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(ddl_tokens)
        cur.execute(ddl_activities)
    conn.commit()
    conn.close()
    return jsonify({"initialized": True})

@app.route("/test-db")
def test_db():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT 1;")
        val = cur.fetchone()[0]
    conn.close()
    return jsonify({"db": val})

@app.route("/test-save-token")
def test_save_token():
    save_token_pg(12345, "dummy-access-token", "dummy-refresh-token")
    return jsonify({"saved": True})

@app.route("/test-get-tokens")
def test_get_tokens():
    tokens = get_tokens_pg(12345)
    return jsonify(tokens or {})

@app.route("/test-save-activity")
def test_save_activity():
    dummy_activity = {
        "id": 999999,
        "athlete": {"id": 12345},
        "name": "Dummy Run",
        "start_date_local": "2025-05-09T00:00:00Z",
        "distance": 1609.34,
        "moving_time": 600,
    }
    save_activity_pg(dummy_activity)
    return jsonify({"saved_activity": True})

@app.route("/test-enrich-activity")
def test_enrich_activity():
    enrich_activity_pg(999999, {"foo": "bar", "updated": True})
    return jsonify({"enriched": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
