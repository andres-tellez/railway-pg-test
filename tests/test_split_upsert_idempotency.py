# tests/test_split_upsert_idempotency.py

from src.db.models.activities import Activity
from src.db.dao.split_dao import upsert_splits
from src.db.models.splits import Split

def test_upsert_splits_idempotency(sqlalchemy_session):
    # Insert parent activity
    activity_id = 55555
    sqlalchemy_session.add(Activity(activity_id=activity_id, athlete_id=1))
    sqlalchemy_session.commit()

    splits = [
        {
            "activity_id": activity_id,
            "lap_index": 1,
            "distance": 1000.0,
            "elapsed_time": 300,
            "moving_time": 290,
            "average_speed": 3.3,
            "max_speed": 3.5,
            "start_index": 0,
            "end_index": 299,
            "split": True
        }
    ]

    # First insert
    inserted = upsert_splits(sqlalchemy_session, splits)
    assert inserted == 1

    # Second insert (should conflict-update, not duplicate)
    inserted_again = upsert_splits(sqlalchemy_session, splits)
    assert inserted_again == 1

    # Verify only 1 row exists
    rows = sqlalchemy_session.query(Split).filter_by(activity_id=activity_id).all()
    assert len(rows) == 1
