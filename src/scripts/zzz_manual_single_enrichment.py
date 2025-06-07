import logging
from src.db.db_session import get_session
from src.services.token_service import ensure_fresh_access_token
from src.services.enrichment_sync import enrich_one_activity

logging.basicConfig(level=logging.INFO)

ATHLETE_ID = 347085
ACTIVITY_ID = 14663194187

session = get_session()
access_token = ensure_fresh_access_token(session, ATHLETE_ID)
enrich_one_activity(session, ATHLETE_ID, access_token, ACTIVITY_ID)
session.close()
