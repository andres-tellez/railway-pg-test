# tests/test_athlete_dao.py

import pytest
from sqlalchemy.orm import Session
from src.db.dao.athlete_dao import (
    insert_athlete,
    get_athlete_by_strava_id,
    get_athlete_id_from_strava_id,
)
from src.db.models.athletes import Athlete


import random


def test_insert_and_get_athlete(test_db_session: Session):
    strava_id = random.randint(100_000_000, 999_999_999)  # ensure uniqueness

    # Insert athlete
    athlete_id = insert_athlete(test_db_session, strava_id)

    # Fetch and verify
    fetched = get_athlete_by_strava_id(test_db_session, strava_id)
    assert fetched is not None
    assert fetched.id == athlete_id
    assert fetched.strava_athlete_id == strava_id

    # Get ID by strava ID
    fetched_id = get_athlete_id_from_strava_id(test_db_session, strava_id)
    assert fetched_id == athlete_id
