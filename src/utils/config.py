import os

# ===== OAuth / Strava =====
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI") or os.getenv("REDIRECT_URI")
STRAVA_API_BASE_URL = "https://www.strava.com/api/v3"

# ===== Token Expiry =====
ACCESS_TOKEN_EXP = int(os.getenv("ACCESS_TOKEN_EXP", "900"))  # 15 min
REFRESH_TOKEN_EXP = int(os.getenv("REFRESH_TOKEN_EXP", "604800"))  # 7 days

# ===== JWT / Auth =====
# Flask app/session secret
SECRET_KEY = os.getenv("SECRET_KEY", "dev")
# For libraries/extensions that expect this key name
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or SECRET_KEY

# ===== Database =====
DATABASE_URL = os.getenv("DATABASE_URL")

# ===== Internal API / Jobs =====
CRON_SECRET_KEY = os.getenv("CRON_SECRET_KEY")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

# ===== Misc =====
PORT = int(os.getenv("PORT", "5000"))
IS_LOCAL = os.getenv("IS_LOCAL", "false").lower() == "true"

# Optional: centralize if you want to import instead of os.getenv in routes
FRONTEND_REDIRECT = os.getenv("FRONTEND_REDIRECT")

# keep everything else you have; ensure these exist:
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")


# ===== Auth0 =====
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
if not AUTH0_DOMAIN:
    raise RuntimeError("Missing AUTH0_DOMAIN in environment configuration")

AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
if not AUTH0_AUDIENCE:
    raise RuntimeError("Missing AUTH0_AUDIENCE in environment configuration")
