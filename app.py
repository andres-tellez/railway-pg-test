from flask           import Flask, jsonify
import os, psycopg2

app = Flask(__name__)

@app.route("/test-db")
def test_db():
    # use the Railway-provided DATABASE_URL
    conn = psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")
    cur  = conn.cursor()
    cur.execute("SELECT version();")
    v = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({"postgres_version": v})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
