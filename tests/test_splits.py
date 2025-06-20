import pytest
from sqlalchemy.exc import IntegrityError
from src.db.db_session import get_session
from src.db.models.splits import Split, upsert_splits
from src.db.models.activities import Activity



@pytest.fixture
def session():
    session = get_session()
    yield session
    session.rollback()
    session.close()

def test_model_instantiation():
    split = Split(
        activity_id=123,
        lap_index=1,
        distance=1000.0,
        elapsed_time=600,
        moving_time=590,
        average_speed=3.4,
        max_speed=5.0,
        split=1,
        average_heartrate=150.0,
        pace_zone=2,
        conv_distance=0.62,
        conv_avg_speed=7.6,
        conv_moving_time="9:50",
        conv_elapsed_time="10:00",
    )
    assert split.activity_id == 123
    assert split.lap_index == 1
    assert split.conv_moving_time == "9:50"

def test_upsert_inserts_and_updates(session):
    # Delete existing activity if present to avoid PK conflict
    existing = session.query(Activity).filter_by(activity_id=1).first()
    if existing:
        session.delete(existing)
        session.commit()

    dummy_activity = Activity(activity_id=1, athlete_id=1, name="Test Activity")
    session.add(dummy_activity)
    session.commit()

    splits_data = [
        {"activity_id": 1, "lap_index": 1, "distance": 1609.34},
        {"activity_id": 1, "lap_index": 2, "distance": 1609.34},
    ]
    upsert_splits(session, splits_data)

    result = session.query(Split).filter(Split.activity_id == 1).all()
    assert len(result) == 2

def test_upsert_empty_list(session):
    # Should not raise or commit anything
    upsert_splits(session, [])
    assert True  # Passed if no exception

def test_unique_constraint(session):
    existing = session.query(Activity).filter_by(activity_id=2).first()
    if existing:
        session.delete(existing)
        session.commit()

    dummy_activity = Activity(activity_id=2, athlete_id=1, name="Another Activity")
    session.add(dummy_activity)
    session.commit()

    split_data = [{"activity_id": 2, "lap_index": 1, "distance": 1000.0}]
    upsert_splits(session, split_data)

    split_data_updated = [{"activity_id": 2, "lap_index": 1, "distance": 1100.0}]
    upsert_splits(session, split_data_updated)

    split = session.query(Split).filter_by(activity_id=2, lap_index=1).one()
    assert split.distance == 1100.0
