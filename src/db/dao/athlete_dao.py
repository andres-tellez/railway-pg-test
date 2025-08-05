# src/db/dao/athlete_dao.py

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.models.athletes import Athlete  # ✅ Import only the ORM class


def get_athlete_by_strava_id(session: Session, strava_id: int) -> Optional[Athlete]:
    """
    Retrieve the athlete record by their Strava athlete ID.
    """
    return session.query(Athlete).filter_by(strava_athlete_id=strava_id).first()


def get_athlete_id_from_strava_id(session: Session, strava_id: int) -> Optional[int]:
    """
    Retrieve internal athlete ID from the Strava athlete ID.
    """
    result = session.query(Athlete.id).filter_by(strava_athlete_id=strava_id).first()
    return result.id if result else None


def insert_athlete(
    session: Session,
    strava_athlete_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
) -> int:
    """
    Insert a new athlete record and return the internal athlete ID.
    """
    new_athlete = Athlete(strava_athlete_id=strava_athlete_id, name=name, email=email)
    session.add(new_athlete)
    session.commit()
    session.refresh(new_athlete)
    return new_athlete.id


def get_all_athletes(session: Session) -> List[Athlete]:
    """
    Retrieve all athletes from the database.
    """
    return session.query(Athlete).all()


def upsert_athlete(
    session: Session,
    athlete_id: int,
    strava_athlete_id: int,
    name: Optional[str],
    email: Optional[str],
) -> None:
    """
    Upsert athlete's name and email using internal athlete ID.
    strava_athlete_id is only used during insert, never updated.
    """
    stmt = (
        pg_insert(Athlete.__table__)
        .values(
            id=athlete_id, strava_athlete_id=strava_athlete_id, name=name, email=email
        )
        .on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": name,
                "email": email,
                # ❌ do NOT include "strava_athlete_id"
            },
        )
    )
    session.execute(stmt)
    session.commit()
