# src/db/dao/athlete_dao.py

from typing import Optional
from sqlalchemy.orm import Session
from src.db.models.athletes import Athlete


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


def insert_athlete(session: Session, strava_athlete_id: int, name: Optional[str] = None, email: Optional[str] = None) -> int:
    """
    Insert a new athlete record and return the internal athlete ID.
    """
    new_athlete = Athlete(
        strava_athlete_id=strava_athlete_id,
        name=name,
        email=email
    )
    session.add(new_athlete)
    session.commit()
    session.refresh(new_athlete)
    return new_athlete.id


def get_all_athletes(session: Session) -> list[Athlete]:
    """
    Retrieve all athletes from the database.
    """
    return session.query(Athlete).all()
