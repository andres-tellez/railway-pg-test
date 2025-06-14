# src/db/dao/athlete_dao.py

from sqlalchemy.orm import Session
from src.db.models.athletes import Athlete

def get_athlete_by_strava_id(session: Session, strava_id: int) -> Athlete | None:
    return session.query(Athlete).filter_by(strava_athlete_id=strava_id).first()

def insert_athlete(session: Session, strava_athlete_id: int, name: str = None, email: str = None) -> int:
    athlete = Athlete(
        strava_athlete_id=strava_athlete_id,
        name=name,
        email=email
    )
    session.add(athlete)
    session.commit()
    session.refresh(athlete)
    return athlete.id

def get_athlete_id_from_strava_id(session: Session, strava_id: int) -> int | None:
    result = session.query(Athlete.id).filter_by(strava_athlete_id=strava_id).first()
    return result.id if result else None
