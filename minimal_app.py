from flask import Flask
from dotenv import load_dotenv
import os

from routes.auth_routes import AUTH
from routes.enrich_routes import ENRICH

# Load local .env
load_dotenv()

# ── Startup‐time env‐var validation ──
REQUIRED_VARS = [
    "DATABASE_URL",
    "STRAVA_CLIENT_ID",
    "STRAVA_CLIENT_SECRET",
    "REDIRECT_URI",
    "CRON_SECRET_KEY",
    "ATHLETE_ID",
]
missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
if missing:
    raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
# ─────────────────────────────────────

app = Flask(__name__)

# Register our new, modular blueprints
app.register_blueprint(AUTH)
app.register_blueprint(ENRICH)


@app.route("/ping")
def ping():
    print("🔍 Received ping")
    return "pong", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
