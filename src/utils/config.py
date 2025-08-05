import os

# ❌ REMOVE this block entirely:
# from dotenv import load_dotenv
# env_mode = os.getenv("FLASK_ENV") or os.getenv("RAILWAY_ENVIRONMENT") or "development"
# env_file = ...
# load_dotenv(env_file, override=True)

# ✅ config.py should only read, never load
# Assume env already set up by app.py

# ----- OAuth / Strava -----
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI") or os.getenv("REDIRECT_URI")
STRAVA_API_BASE_URL = "https://www.strava.com/api/v3"

# ----- Token Expiry -----
ACCESS_TOKEN_EXP = int(os.getenv("ACCESS_TOKEN_EXP", 900))  # 15 min
REFRESH_TOKEN_EXP = int(os.getenv("REFRESH_TOKEN_EXP", 604800))  # 7 days

# ----- JWT / Auth -----
SECRET_KEY = os.getenv("SECRET_KEY", "dev")
JWT_SECRET_KEY = SECRET_KEY  # 🔄 standardize naming to match Flask-JWT usage
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
ADMIN_ATHLETE_ID = int(os.getenv("ADMIN_ATHLETE_ID", "0"))

# ----- Database -----
DATABASE_URL = os.getenv("DATABASE_URL")

# ----- Internal API / Jobs -----
CRON_SECRET_KEY = os.getenv("CRON_SECRET_KEY")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

# ----- Misc -----
PORT = int(os.getenv("PORT", 5000))
IS_LOCAL = os.getenv("IS_LOCAL", "false").lower() == "true"

JWT_SECRET = SECRET_KEY
