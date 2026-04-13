"""DAO for durable Strava ingestion retry rows."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import List, NamedTuple

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from src.db.db_session import get_session
from src.db.models.strava_ingestion_retry import StravaIngestionRetry

logger = logging.getLogger(__name__)

STALE_CLAIM_MINUTES = 25


class RetryClaim(NamedTuple):
    id: int
    user_id: str
    athlete_id: int
    attempt: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def upsert_pending_retry(
    session: Session,
    user_id: str,
    athlete_id: int,
    delay_sec: float,
    attempt: int,
) -> bool:
    """
    Schedule a retry at now + delay (+ jitter). If an unclaimed future run is
    already queued (same semantics as the old in-memory timer duplicate skip),
    return False and leave the row unchanged.
    """
    uid = str(user_id)
    delay_sec = max(30.0, float(delay_sec))
    jitter = random.uniform(0.0, 20.0)
    run_after = _utcnow() + timedelta(seconds=delay_sec + jitter)

    row = (
        session.query(StravaIngestionRetry)
        .filter(
            StravaIngestionRetry.user_id == uid,
            StravaIngestionRetry.athlete_id == int(athlete_id),
        )
        .with_for_update(of=StravaIngestionRetry)
        .first()
    )

    if row and row.claimed_at is None and row.run_after > _utcnow():
        logger.info(
            "Strava retry already queued user=%s athlete=%s run_after=%s; skip",
            uid,
            athlete_id,
            row.run_after.isoformat(),
        )
        session.rollback()
        return False

    if row:
        row.run_after = run_after
        row.attempt = int(attempt)
    else:
        session.add(
            StravaIngestionRetry(
                user_id=uid,
                athlete_id=int(athlete_id),
                run_after=run_after,
                attempt=int(attempt),
            )
        )
    session.commit()
    logger.info(
        "Queued durable Strava ingestion retry user=%s athlete=%s run_after=%s attempt=%s",
        uid,
        athlete_id,
        run_after.isoformat(),
        attempt,
    )
    return True


def delete_retry_for_user_athlete(
    session: Session, user_id: str, athlete_id: int
) -> None:
    session.execute(
        delete(StravaIngestionRetry).where(
            StravaIngestionRetry.user_id == str(user_id),
            StravaIngestionRetry.athlete_id == int(athlete_id),
        )
    )
    session.commit()


def delete_retry_standalone(user_id: str, athlete_id: int) -> None:
    """Separate transaction so callers do not poison an open orchestrator session."""
    s = get_session()
    try:
        delete_retry_for_user_athlete(s, str(user_id), int(athlete_id))
    except Exception as exc:
        logger.warning(
            "delete_retry_standalone failed user=%s athlete=%s: %s",
            user_id,
            athlete_id,
            exc,
        )
        s.rollback()
    finally:
        s.close()


def release_claim_standalone(user_id: str, athlete_id: int) -> None:
    s = get_session()
    try:
        release_claim(s, str(user_id), int(athlete_id))
    except Exception as exc:
        logger.warning(
            "release_claim_standalone failed user=%s athlete=%s: %s",
            user_id,
            athlete_id,
            exc,
        )
        s.rollback()
    finally:
        s.close()


def release_claim(session: Session, user_id: str, athlete_id: int) -> None:
    row = (
        session.query(StravaIngestionRetry)
        .filter(
            StravaIngestionRetry.user_id == str(user_id),
            StravaIngestionRetry.athlete_id == int(athlete_id),
        )
        .first()
    )
    if row:
        row.claimed_at = None
        session.commit()


def reclaim_stale_claims(session: Session) -> int:
    cutoff = _utcnow() - timedelta(minutes=STALE_CLAIM_MINUTES)
    rows = (
        session.query(StravaIngestionRetry)
        .filter(
            StravaIngestionRetry.claimed_at.isnot(None),
            StravaIngestionRetry.claimed_at < cutoff,
        )
        .all()
    )
    for r in rows:
        r.claimed_at = None
    if rows:
        session.commit()
    return len(rows)


def claim_due_retries(session: Session, *, limit: int = 10) -> List[RetryClaim]:
    """
    Mark up to `limit` due rows as claimed and return them. Caller runs ingestion
    and must call release_claim or delete_retry when finished.
    """
    reclaim_stale_claims(session)

    dialect = session.get_bind().dialect.name
    now = _utcnow()

    if dialect == "postgresql":
        rows = session.execute(
            text(
                """
                UPDATE strava_ingestion_retry AS t
                SET claimed_at = NOW()
                FROM (
                    SELECT id FROM strava_ingestion_retry
                    WHERE run_after <= NOW()
                      AND claimed_at IS NULL
                    ORDER BY run_after
                    LIMIT :lim
                    FOR UPDATE SKIP LOCKED
                ) AS sub
                WHERE t.id = sub.id
                RETURNING t.id, t.user_id, t.athlete_id, t.attempt
                """
            ),
            {"lim": limit},
        ).all()
        session.commit()
        return [RetryClaim(int(r[0]), str(r[1]), int(r[2]), int(r[3])) for r in rows]

    # SQLite / tests: single-threaded claim without SKIP LOCKED
    rows = (
        session.query(StravaIngestionRetry)
        .filter(
            StravaIngestionRetry.run_after <= now,
            StravaIngestionRetry.claimed_at.is_(None),
        )
        .order_by(StravaIngestionRetry.run_after)
        .limit(limit)
        .with_for_update()
        .all()
    )
    out: List[RetryClaim] = []
    for r in rows:
        r.claimed_at = now
        out.append(RetryClaim(r.id, str(r.user_id), int(r.athlete_id), int(r.attempt)))
    session.commit()
    return out
