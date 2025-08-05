# tests/test_split_dao.py

import pytest
from src.db.dao.split_dao import upsert_splits
from src.db.models.splits import Split
from src.db.models.activities import Activity  # ✅ Import Activity to insert FK parent


def test_upsert_splits_basic(sqlalchemy_session):
    # ✅ Insert parent Activity row to satisfy ForeignKey constraint
    sqlalchemy_session.add(Activity(activity_id=123, athlete_id=1))
    sqlalchemy_session.commit()

    splits = [
        {
            "activity_id": 123,
            "lap_index": 1,
            "distance": 1000.0,
            "elapsed_time": 300,
            "moving_time": None,
            "average_speed": 3.33,
            "max_speed": None,
            "start_index": None,
            "end_index": None,
            "split": 1,  # Ensure it's stored as INTEGER
        },
        {
            "activity_id": 123,
            "lap_index": 2,
            "distance": 1000.0,
            "elapsed_time": 320,
            "moving_time": None,
            "average_speed": 3.12,
            "max_speed": None,
            "start_index": None,
            "end_index": None,
            "split": 2,  # Ensure it's stored as INTEGER
        },
    ]

    # ✅ Perform the upsert
    inserted = upsert_splits(sqlalchemy_session, splits)
    assert inserted == 2

    # ✅ Verify inserted rows
    rows = (
        sqlalchemy_session.query(Split)
        .filter_by(activity_id=123)
        .order_by(Split.lap_index)
        .all()
    )
    assert len(rows) == 2
    assert rows[0].lap_index == 1
    assert rows[0].distance == 1000.0
    assert rows[0].elapsed_time == 300
    assert rows[0].average_speed == 3.33
    assert isinstance(rows[0].split, int)
