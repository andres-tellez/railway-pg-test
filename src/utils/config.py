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
    STRAVA_PER_PAGE = int(os.getenv("STRAVA_PER_PAGE", 200))  # Strava API limit is 200

    # ===== Strava API Retry Settings =====
    STRAVA_MAX_RETRIES = int(
        os.getenv("STRAVA_MAX_RETRIES", 5)
    )  # Max retries for API requests
    STRAVA_INITIAL_BACKOFF = int(
        os.getenv("STRAVA_INITIAL_BACKOFF", 10)
    )  # Initial backoff in seconds

    # ===== Ingestion / enrichment =====
    # When false, enrichment skips Strava stream fetch and split/lap persistence (activity rows unchanged).
    ENABLE_SPLITS = os.getenv("ENABLE_SPLITS", "true").lower() in ("true", "1", "yes")

    # ===== Ingestion Defaults =====
    DEFAULT_LOOKBACK_DAYS = int(
        os.getenv("DEFAULT_LOOKBACK_DAYS", 365)
    )  # Default days to look back
    DEFAULT_BATCH_SIZE = int(
        os.getenv("DEFAULT_BATCH_SIZE", 50)
    )  # Default batch size for enrichment
    # Max enrichment batches per ingest chunk (each batch processes up to DEFAULT_BATCH_SIZE activities).
    MAX_ENRICHMENT_BATCHES_PER_CHUNK = int(
        os.getenv("MAX_ENRICHMENT_BATCHES_PER_CHUNK", "25")
    )
    DEFAULT_PER_PAGE = int(
        os.getenv("DEFAULT_PER_PAGE", 50)
    )  # Default activities per page

    # ===== SmartCoach MVP (HTTP proxy; no duplicated coach logic) =====
    SMARTCOACH_BASE_URL = (os.getenv("SMARTCOACH_BASE_URL") or "").strip() or None
    SMARTCOACH_TIMEOUT_SECONDS = float(os.getenv("SMARTCOACH_TIMEOUT_SECONDS", "60"))
    # Optional cap when resolving a run by local calendar date (0 = unlimited)
    SMARTCOACH_DATE_LOOKBACK_DAYS = int(os.getenv("SMARTCOACH_DATE_LOOKBACK_DAYS", "0"))


# Export single instance for import convenience
config = Config()
