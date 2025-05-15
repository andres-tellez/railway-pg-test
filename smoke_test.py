# smoke_test.py

import os
from flask import Flask

# this must match what you point Gunicorn at in Procfile:
smoke = Flask(__name__)

@smoke.route("/")
def home():
    return "🚂 Smoke test v3!"

@smoke.route("/test-connect")
def test_connect():
    return "Test endpoint v3 OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    smoke.run(host="0.0.0.0", port=port)
