# src/utils/seeder.py

from src.db.dao.activity_dao import ActivityDAO
from tests.test_data.sample_activities import SAMPLE_ACTIVITY_JSON

def seed_sample_activity(session, athlete_id: int):
    mock = SAMPLE_ACTIVITY_JSON.copy()
    mock["athlete_id"] = athlete_id
    mock["id"] = mock["activity_id"] = 99999 + athlete_id  # ensure unique PK
    ActivityDAO.upsert_activities(session, athlete_id, [mock])
