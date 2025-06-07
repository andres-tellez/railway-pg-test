from datetime import datetime
from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa
from src.db.models.tokens import Token
from src.services.strava_client import StravaClient

def ensure_fresh_access_token(session, athlete_id: int) -> str:
    """
    Centralized token refresh handler. Returns valid access token.
    """
    tokens = get_tokens_sa(session, athlete_id)
    if not tokens:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    now_ts = int(datetime.utcnow().timestamp())
    token_record = session.query(Token).filter_by(athlete_id=athlete_id).one()

    if token_record.expires_at > now_ts:
        return tokens["access_token"]

    # Token expired — refresh and persist updated tokens
    refreshed = StravaClient.refresh_token_static(tokens["refresh_token"])
    save_tokens_sa(
        session,
        athlete_id,
        refreshed["access_token"],
        refreshed["refresh_token"],
        refreshed["expires_at"]
    )
    return refreshed["access_token"]
