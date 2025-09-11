# src/db/dao/user_athletes_dao.py
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.db_session import get_session
from src.db.models.user_athletes import UserAthlete
from src.db.models.user_identity import UserIdentity  # ✅ FIXED


def _validate_user_exists(session: Session, user_id: str) -> None:
    """Ensure the internal UUID user ID exists in user_identity."""  # ✅ FIXED DOCSTRING
    row = session.execute(
        select(UserIdentity.user_id).where(UserIdentity.user_id == str(user_id))
    ).first()
    if not row:
        raise ValueError(f"user_id '{user_id}' not present in user_identity.user_id")


def create_link(user_id: str, athlete_id: int) -> UserAthlete:
    """
    Create/link user -> athlete. 'user_id' is the external Auth0 sub string.
    """
    with get_session() as session:
        _validate_user_exists(session, user_id)
        row = UserAthlete(user_id=user_id, athlete_id=athlete_id)
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = (
                session.query(UserAthlete)
                .filter_by(user_id=user_id)  # 1:1 on user side
                .first()
            )
            if existing:
                return existing
            raise
        session.refresh(row)
        return row


def get_all_athlete_ids(session: Session) -> List[int]:
    result = session.query(UserAthlete.athlete_id).distinct().all()
    return [r.athlete_id for r in result]


def get_by_user_id(user_id: str) -> Optional[UserAthlete]:
    with get_session() as session:
        return session.query(UserAthlete).filter_by(user_id=user_id).first()


def get_by_athlete_id(athlete_id: int) -> Optional[UserAthlete]:
    with get_session() as session:
        return session.query(UserAthlete).filter_by(athlete_id=athlete_id).first()


def delete_by_user_id(user_id: str) -> int:
    with get_session() as session:
        res = session.execute(delete(UserAthlete).where(UserAthlete.user_id == user_id))
        session.commit()
        return res.rowcount or 0
