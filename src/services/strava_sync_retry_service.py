"""
Durable deferred Strava ingestion retries (e.g. rate-limit headroom abort).

Persists the next run time in Postgres so retries survive process restarts.
A cron job (or Railway recurring task) should POST to the internal processor
endpoint periodically — see `src/routes/internal_cron_routes.py`.
"""

from __future__ import annotations

import logging
import threading

from src.db.dao.strava_ingestion_retry_dao import (
    claim_due_retries,
    delete_retry_standalone,
    release_claim_standalone,
    upsert_pending_retry,
)
from src.db.db_session import get_session

logger = logging.getLogger(__name__)


def schedule_strava_ingestion_retry(
    user_id: str, athlete_id: int, delay_sec: float, attempt: int
) -> None:
    """
    Queue run_full_ingestion_and_enrichment after delay_sec (+ jitter).

    Duplicate schedules for the same (user_id, athlete_id) are suppressed when
    an unclaimed future row already exists (same semantics as the old in-memory
    timer).
    """
    if not user_id:
        logger.warning("schedule_strava_ingestion_retry: missing user_id; skip")
        return

    session = get_session()
    try:
        upsert_pending_retry(
            session, str(user_id), int(athlete_id), delay_sec, int(attempt)
        )
    except Exception as exc:
        session.rollback()
        logger.error(
            "Failed to persist Strava ingestion retry user=%s athlete=%s: %s",
            user_id,
            athlete_id,
            exc,
            exc_info=True,
        )
    finally:
        session.close()


def _run_claimed_ingestion(uid: str, aid: int, att: int) -> None:
    from src.services.ingestion_orchestrator_service import (
        run_full_ingestion_and_enrichment,
    )

    try:
        out = run_full_ingestion_and_enrichment(
            None, aid, user_id=uid, sync_retry_attempt=int(att)
        )
        if isinstance(out, dict) and out.get("deferred"):
            return
    except Exception:
        delete_retry_standalone(uid, aid)
        raise
    finally:
        release_claim_standalone(uid, aid)


def process_due_strava_ingestion_retries(*, limit: int = 10) -> int:
    """
    Claim due rows and start background ingestion jobs. Safe to call from a
    cron every minute. Returns number of jobs started.
    """
    claims = []
    session = get_session()
    try:
        claims = claim_due_retries(session, limit=limit)
    except Exception as exc:
        session.rollback()
        logger.error("claim_due_retries failed: %s", exc, exc_info=True)
        return 0
    finally:
        session.close()

    from src.utils.strava_helpers import run_background_job

    for c in claims:

        def job(
            sess,
            athlete_id=c.athlete_id,
            user_id=c.user_id,
            attempt=c.attempt,
        ) -> None:
            _ = sess  # run_full_ingestion_and_enrichment opens its own session
            _run_claimed_ingestion(user_id, athlete_id, attempt)

        run_background_job(job, c.athlete_id, c.user_id, c.attempt)

    if claims:
        logger.info("Started %s durable Strava ingestion retry job(s)", len(claims))
    return len(claims)
