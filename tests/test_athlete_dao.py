# tests/test_athlete_dao.py

import pytest
from sqlalchemy.orm import Session
from src.db.dao.athlete_dao import (
    insert_athlete,
    get_athlete_by_strava_id,
    get_athlete_id_from_strava_id,
)
from src.db.models.athletes import Athlete


def test_insert_and_get_athlete(test_db_session: Session):
    strava_id = 123456789
    name = "Test User"
    email = "test@example.com"

    # Insert athlete
    athlete_id = insert_athlete(test_db_session, strava_id, name, email)
    assert isinstance(athlete_id, int)

    # Get full athlete
    athlete = get_athlete_by_strava_id(test_db_session, strava_id)
    assert athlete is not None
    assert athlete.name == name
    assert athlete.email == email

    # Get ID by strava ID
    fetched_id = get_athlete_id_from_strava_id(test_db_session, strava_id)
    assert fetched_id == athlete_id
