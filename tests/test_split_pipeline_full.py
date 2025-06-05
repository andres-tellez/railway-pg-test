from src.db.models.activities import Activity
from src.db.dao.split_dao import upsert_splits
from src.services.split_extraction import extract_splits
from src.db.models.splits import Split

def test_full_split_pipeline(sqlalchemy_session):
    """
    Full pipeline: activity → extract_splits → upsert_splits → verify DB
    """
    # Seed parent activity (FK constraint)
    activity = Activity(activity_id=98765, athlete_id=42)
    sqlalchemy_session.add(activity)
    sqlalchemy_session.commit()

    # Simulate Strava activity payload
    sample_activity = {
        "id": 98765,
        "splits_metric": [
            {"split": 1, "distance": 1000, "elapsed_time": 300, "average_speed": 3.3},
            {"split": 2, "distance": 1000, "elapsed_time": 310, "average_speed": 3.2},
            {"split": 3, "distance": 1000, "elapsed_time": 315, "average_speed": 3.1}
        ]
    }

    # Extraction
    splits = extract_splits(sample_activity)
    assert len(splits) == 3

    # DAO upsert
    count = upsert_splits(sqlalchemy_session, splits)
    assert count == 3

    # Verify DB contents
    rows = sqlalchemy_session.query(Split).filter_by(activity_id=98765).all()
    assert len(rows) == 3
