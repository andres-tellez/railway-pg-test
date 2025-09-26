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


def create_link(user_id: str, athlete_id: int) -> UserAthleteLink:
    """
    Create/link user -> athlete. 'user_id' is the internal UUID.
    """
    with get_session() as session:
        _validate_user_exists(session, user_id)
        row = UserAthleteLink(user_id=user_id, athlete_id=athlete_id)
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = (
                session.query(UserAthleteLink)
                .filter_by(user_id=user_id)  # 1:1 on user side
                .first()
            )
            if existing:
                return existing
            raise
        session.refresh(row)
        return row


def get_all_athlete_ids(session: Session) -> List[int]:
    result = session.query(UserAthleteLink.athlete_id).distinct().all()
    return [r.athlete_id for r in result]


def get_by_user_id(user_id: str) -> Optional[UserAthleteLink]:
    with get_session() as session:
        return session.query(UserAthleteLink).filter_by(user_id=user_id).first()


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
