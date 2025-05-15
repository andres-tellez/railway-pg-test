# minimal_app.py
import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "🚂 Smoke test v3!"

@app.route("/test-connect")
def test_connect():
    return "Test endpoint v3 OK", 200

if __name__ == "__main__":
    # local dev fallback
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
