# src/db/dao/user_athletes_dao.py
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.db_session import get_session
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.user_identity import UserIdentity
import uuid


def _validate_user_exists(session: Session, user_id: str) -> None:
    """Ensure the internal UUID user ID exists in user_identity."""
    row = session.execute(
        select(UserIdentity.user_id).where(UserIdentity.user_id == str(user_id))
    ).first()
    if not row:
        raise ValueError(f"user_id '{user_id}' not present in user_identity.user_id")


def create_link(
    user_id: str, athlete_id: int, session: Optional[Session] = None
) -> UserAthleteLink:
    """
    Create/link user -> athlete. 'user_id' is the internal UUID.

    Args:
        user_id: Internal UUID user ID
        athlete_id: Strava athlete ID
        session: Optional session to use. If None, creates a new session.

    Returns:
        UserAthleteLink instance
    """
    should_close = False
    if session is None:
        session = get_session().__enter__()
        should_close = True

    try:
        _validate_user_exists(session, user_id)
        row = UserAthleteLink(user_id=user_id, athlete_id=athlete_id)
        session.add(row)
        try:
            if should_close:
                session.commit()
            # If session is provided, flush to check for IntegrityError without committing
            else:
                session.flush()
        except IntegrityError:
            # Rollback the add operation
            session.rollback()
            # Check if link already exists
            existing = (
                session.query(UserAthleteLink)
                .filter_by(user_id=user_id)  # 1:1 on user side
                .first()
            )
            if existing:
                if should_close:
                    session.close()
                return existing
            raise
        if should_close:
            session.refresh(row)
            session.close()
        return row
    except Exception:
        if should_close:
            session.rollback()
            session.close()
        raise


def get_all_athlete_ids(session: Session) -> List[int]:
    result = session.query(UserAthleteLink.athlete_id).distinct().all()
    return [r.athlete_id for r in result]


def get_by_user_id(user_id: str) -> Optional[UserAthleteLink]:
    import logging

    logger = logging.getLogger(__name__)

    # Ensure user_id is a string
    user_id_str = str(user_id) if user_id else None
    if not user_id_str:
        print(f"[DEBUG] ⚠️ get_by_user_id called with None or empty user_id")
        return None

    print(
        f"[DEBUG] 🔎 get_by_user_id querying for user_id={user_id_str} (type: {type(user_id).__name__})"
    )

    with get_session() as session:
        # Try querying with string
        link = session.query(UserAthleteLink).filter_by(user_id=user_id_str).first()

        if link:
            print(
                f"[DEBUG] ✅ Found link: user_id={link.user_id} (type: {type(link.user_id).__name__}), athlete_id={link.athlete_id}"
            )
        else:
            print(f"[DEBUG] ❌ No link found for user_id={user_id_str}")
            # Debug: check all links
            all_links = session.query(UserAthleteLink).all()
            print(f"[DEBUG]    Total links in DB: {len(all_links)}")
            if all_links:
                for i, l in enumerate(all_links[:3]):  # Show first 3
                    print(
                        f"[DEBUG]    Link {i+1}: user_id={l.user_id} (type: {type(l.user_id).__name__}), athlete_id={l.athlete_id}"
                    )

        return link


def get_by_athlete_id(athlete_id: int) -> Optional[UserAthleteLink]:
    with get_session() as session:
        return session.query(UserAthleteLink).filter_by(athlete_id=athlete_id).first()


def delete_by_user_id(user_id: str) -> int:
    with get_session() as session:
        res = session.execute(
            delete(UserAthleteLink).where(UserAthleteLink.user_id == user_id)
        )
        session.commit()
        return res.rowcount or 0


def get_user_id_for_athlete(session: Session, athlete_id: int) -> Optional[uuid.UUID]:
    """
    Given an athlete_id (int, from Strava), return the linked internal user_id (UUID).
    """
    row = (
        session.query(UserAthleteLink.user_id).filter_by(athlete_id=athlete_id).first()
    )
    if not row:
        return None

    user_id = row[0]

    # ✅ Ensure it's always a UUID
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except Exception:
        raise ValueError(f"Invalid user_id stored for athlete {athlete_id}: {user_id}")
