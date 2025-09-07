import pytest
from sqlalchemy.exc import IntegrityError
from src.db.dao.user_athletes_dao import create_link, get_by_user_id, delete_by_user_id
from src.db.models.athletes import Athlete
from src.db.db_session import get_session


def make_athlete():
    with get_session() as s:
        import random

        a = Athlete(strava_athlete_id=random.randint(100_000_000, 999_999_999))
        s.add(a)
        s.commit()
        s.refresh(a)
        return a


def test_create_and_get_link():
    a = make_athlete()
    row = create_link("auth0|user_1", a.id)
    assert row.user_id == "auth0|user_1"
    assert row.athlete_id == a.id
    assert get_by_user_id("auth0|user_1").athlete_id == a.id


def test_unique_conflicts():
    a1, a2 = make_athlete(), make_athlete()
    create_link("auth0|x", a1.id)
    with pytest.raises(IntegrityError):
        create_link("auth0|x", a2.id)  # same user, different athlete
    with pytest.raises(IntegrityError):
        create_link("auth0|y", a1.id)  # different user, same athlete


def test_delete_by_user_id():
    a = make_athlete()
    create_link("auth0|z", a.id)
    assert delete_by_user_id("auth0|z") == 1
    assert delete_by_user_id("auth0|z") == 0
