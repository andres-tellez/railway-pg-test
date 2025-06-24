import os
from dotenv import load_dotenv

# ----- Dynamic .env loading logic -----

# Use FLASK_ENV or fallback to RAILWAY_ENVIRONMENT or default to "development"
env_mode = os.getenv("FLASK_ENV") or os.getenv("RAILWAY_ENVIRONMENT") or "development"

if env_mode == "testing":
    env_file = ".env.test"
elif env_mode == "production":
    env_file = ".env.prod"
else:
    env_file = ".env"

# Load the selected environment file
load_dotenv(env_file, override=True)
print(f"✅ Loaded environment: {env_file}")

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
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
ADMIN_ATHLETE_ID = 0  # Constant for system user

# ----- Database -----
DATABASE_URL = os.getenv("DATABASE_URL")

# ----- Internal API / Jobs -----
CRON_SECRET_KEY = os.getenv("CRON_SECRET_KEY")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

# ----- Misc -----
PORT = int(os.getenv("PORT", 5000))
IS_LOCAL = os.getenv("IS_LOCAL", "false").lower() == "true"
