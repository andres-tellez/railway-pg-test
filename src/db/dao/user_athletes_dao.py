# src/db/dao/user_athletes_dao.py
from sqlalchemy import select, insert, delete
from sqlalchemy.exc import IntegrityError
from src.db.db_session import get_session
from src.db.models.user_athletes import UserAthlete


def create_link(user_id: str, athlete_id: int) -> UserAthlete:
    """Create a strict 1:1 link. Raises IntegrityError on conflicts.
    Returns an ORM row with .user_id / .athlete_id attributes (not a dict).
    """
    with get_session() as session:
        row = UserAthlete(user_id=user_id, athlete_id=athlete_id)
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise
        session.refresh(row)
        return row


def get_by_user_id(user_id: str) -> UserAthlete | None:
    """Return an ORM row (or None), not a dict."""
    with get_session() as session:
        res = (
            session.execute(select(UserAthlete).where(UserAthlete.user_id == user_id))
            .scalars()
            .first()
        )
        return res


def get_by_athlete_id(athlete_id: int) -> UserAthlete | None:
    """Return an ORM row (or None), not a dict."""
    with get_session() as session:
        res = (
            session.execute(
                select(UserAthlete).where(UserAthlete.athlete_id == athlete_id)
            )
            .scalars()
            .first()
        )
        return res


def delete_by_user_id(user_id: str) -> int:
    with get_session() as session:
        res = session.execute(delete(UserAthlete).where(UserAthlete.user_id == user_id))
        session.commit()
        return res.rowcount or 0
