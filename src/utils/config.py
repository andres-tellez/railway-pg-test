# src/utils/config.py
import os


class Config:
    # ===== OAuth / Strava =====
    STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
    STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI") or os.getenv("REDIRECT_URI")
    STRAVA_API_BASE_URL = "https://www.strava.com/api/v3"

    # ===== Token Expiry =====
    ACCESS_TOKEN_EXP = int(os.getenv("ACCESS_TOKEN_EXP", "900"))  # 15 min
    REFRESH_TOKEN_EXP = int(os.getenv("REFRESH_TOKEN_EXP", "604800"))  # 7 days

    # ===== JWT / Auth =====
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "unused-secret")

    # ===== Auth0 =====
    AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
    AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
    AUTH0_ISSUER = os.getenv("AUTH0_ISSUER")
    AUTH0_ALGORITHMS = os.getenv("AUTH0_ALGORITHMS", "RS256")

    # ===== Internal API / Jobs =====
    CRON_SECRET_KEY = os.getenv("CRON_SECRET_KEY", "")
    INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

    # ===== Database =====
    DATABASE_URL = os.getenv("DATABASE_URL")

    # ===== Misc =====
    PORT = int(os.getenv("PORT", "5000"))
    IS_LOCAL = os.getenv("IS_LOCAL", "false").lower() == "true"
    FRONTEND_REDIRECT = os.getenv("FRONTEND_REDIRECT")


# Export single instance for import convenience
config = Config()
