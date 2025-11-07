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

    # ===== Auth0 =====
    AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
    AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
    AUTH0_ISSUER = os.getenv("AUTH0_ISSUER")
    AUTH0_ALGORITHMS = os.getenv("AUTH0_ALGORITHMS", "RS256")

    # ===== Database =====
    DATABASE_URL = os.getenv("DATABASE_URL")

    # ===== Misc =====
    PORT = int(os.getenv("PORT", "5000"))
    IS_LOCAL = os.getenv("IS_LOCAL", "false").lower() == "true"
    FRONTEND_REDIRECT = os.getenv("FRONTEND_REDIRECT")

    # ===== Business Rules =====
    MIN_ACTIVITIES_REQUIRED = int(os.getenv("MIN_ACTIVITIES_REQUIRED", 1))
    MAX_ACTIVITIES_TO_DOWNLOAD = int(os.getenv("MAX_ACTIVITIES_TO_DOWNLOAD", 50))
    STRAVA_PER_PAGE = int(os.getenv("STRAVA_PER_PAGE", 200))  # Strava API limit is 200

    # ===== Strava API Retry Settings =====
    STRAVA_MAX_RETRIES = int(
        os.getenv("STRAVA_MAX_RETRIES", 5)
    )  # Max retries for API requests
    STRAVA_INITIAL_BACKOFF = int(
        os.getenv("STRAVA_INITIAL_BACKOFF", 10)
    )  # Initial backoff in seconds

    # ===== Ingestion Defaults =====
    DEFAULT_LOOKBACK_DAYS = int(
        os.getenv("DEFAULT_LOOKBACK_DAYS", 365)
    )  # Default days to look back
    DEFAULT_BATCH_SIZE = int(
        os.getenv("DEFAULT_BATCH_SIZE", 50)
    )  # Default batch size for enrichment
    DEFAULT_PER_PAGE = int(
        os.getenv("DEFAULT_PER_PAGE", 50)
    )  # Default activities per page


# Export single instance for import convenience
config = Config()
