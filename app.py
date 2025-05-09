import os
import psycopg2
from flask import Flask, jsonify

app = Flask(__name__)

def get_conn():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set!")
    return psycopg2.connect(db_url, sslmode="require")

@app.route("/test-db")
def test_db():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT 1;")
        val = cur.fetchone()[0]
    conn.close()
    return jsonify({"db": val})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
