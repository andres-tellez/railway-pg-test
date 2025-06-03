from datetime import datetime, timedelta
import json
from src.utils.logger import get_logger
from src.services.strava import fetch_activities_between, refresh_strava_token
from src.db.dao.activity_dao import upsert_activities
from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa
from src.db.models.tokens import Token

log = get_logger(__name__)

def ensure_fresh_token(session, athlete_id: int) -> str:
    """
    Ensure we have a valid access token for the athlete.
    Refresh token automatically if expired.
    """
    tokens = get_tokens_sa(session, athlete_id)
    if not tokens:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    now_ts = int(datetime.utcnow().timestamp())
    token_record = session.query(Token).filter_by(athlete_id=athlete_id).one()

    if token_record.expires_at > now_ts:
        return tokens["access_token"]  # token still valid

    # Token expired — refresh
    log.info(f"Refreshing expired token for athlete {athlete_id}")
    refreshed = refresh_strava_token(tokens["refresh_token"])
    save_tokens_sa(session, athlete_id, refreshed["access_token"], refreshed["refresh_token"], refreshed["expires_at"])
    return refreshed["access_token"]

def sync_activities_between(session, athlete_id: int, access_token: str, start_date: datetime, end_date: datetime, per_page=200, max_activities=None) -> int:
    """
    Generic ingestion engine: Fetch and store activities for a given athlete between the specified dates.
    Supports optional max_activities limit for controlled backfill tests.
    """
    try:
        all_activities = []
        page = 1

        while True:
            activities = fetch_activities_between(access_token, start_date, end_date, per_page=per_page)
            if not activities:
                break

            all_activities.extend(activities)

            if max_activities and len(all_activities) >= max_activities:
                all_activities = all_activities[:max_activities]
                break

            # Check if fewer than per_page returned, meaning no more pages
            if len(activities) < per_page:
                break

            page += 1

        if not all_activities:
            log.info(f"No activities found for athlete {athlete_id} between {start_date.date()} and {end_date.date()}")
            return 0

        count = upsert_activities(session, athlete_id, all_activities)
        log.info(f"Synced {count} activities for athlete {athlete_id} between {start_date.date()} and {end_date.date()}")
        return count

    except Exception as e:
        raise RuntimeError(f"Failed to fetch or persist activities: {e}")

def sync_recent(session, athlete_id: int, access_token: str) -> int:
    """
    Scheduled sync: Pull last 7 days of activities (incremental sync).
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    return sync_activities_between(session, athlete_id, access_token, start_date, end_date)

def sync_full_history(session, athlete_id: int, access_token: str, lookback_days: int = 730, max_activities=None) -> int:
    """
    Full historical backfill: Pull activities over entire historical window.
    Default to 2 years lookback, configurable.
    Optional: limit total activities pulled for pilot testing.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    return sync_activities_between(session, athlete_id, access_token, start_date, end_date, max_activities=max_activities)

def enrich_missing_activities(session, athlete_id: int):
    """
    Placeholder enrichment function.
    Enrichment pipeline will be implemented in Phase 2.
    """
    log.info("Enriching activities is not yet implemented in MVP.")
    return 0
