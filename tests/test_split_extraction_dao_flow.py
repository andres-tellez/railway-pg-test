# tests/test_split_extraction_dao_flow.py

from src.db.dao.split_dao import upsert_splits
from src.db.models.splits import Split
from src.db.models.activities import Activity  # ✅ NEW IMPORT - FK support
from src.services.split_extraction import extract_splits


def test_split_extraction_and_upsert(sqlalchemy_session):
    # ✅ Insert parent activity first to satisfy FK constraint
    sqlalchemy_session.add(Activity(activity_id=555, athlete_id=1))
    sqlalchemy_session.commit()

    # Sample activity input with splits
    sample_activity = {
        "id": 555,
        "splits_metric": [
            {"split": 1, "distance": 1000, "elapsed_time": 300, "average_speed": 3.3},
            {"split": 2, "distance": 1000, "elapsed_time": 310, "average_speed": 3.2}
        ]
    }

    # ✅ Extract splits
    splits = extract_splits(sample_activity)

    # ✅ Upsert extracted splits into DB
    count = upsert_splits(sqlalchemy_session, splits)

    assert count == 2

    # ✅ Query DB and validate inserted splits
    rows = sqlalchemy_session.query(Split).filter_by(activity_id=555).order_by(Split.lap_index).all()
    assert len(rows) == 2
    assert rows[0].lap_index == 1
    assert rows[0].distance == 1000
    assert rows[0].elapsed_time == 300
    assert rows[0].average_speed == 3.3
