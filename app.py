"""
railway-pg-test: simple Flask + Postgres smoke test
Routes:
 - /debug-env : dumps the key env vars
 - /test-db   : runs SELECT 1 against DATABASE_URL
"""

import os
import logging
import psycopg2
from flask import Flask, jsonify
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set!")
    conn = psycopg2.connect(db_url, sslmode="require")
    # ensure public schema
    with conn.cursor() as cur:
        cur.execute("SET search_path TO public;")
    return conn

@app.route("/debug-env")
def debug_env():
    keys = ["DATABASE_URL","PGHOST","PGPORT","PGUSER","PGPASSWORD","PGDATABASE"]
    return jsonify({k: os.getenv(k) for k in keys})

@app.route("/test-db")
def test_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            val = cur.fetchone()[0]
        conn.close()
        return jsonify({"db": val})
    except Exception as e:
        logging.error(f"/test-db error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # local debug only
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
