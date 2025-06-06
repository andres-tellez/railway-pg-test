# src/scripts/dev_seed_data.py

from sqlalchemy.orm import Session
from src.db.db_session import get_engine
from src.db.models.activities import Activity
from src.db.models.splits import Split


# Use your local Postgres DB
DATABASE_URL = "postgresql+psycopg2://smartcoach:devpass@localhost:15432/smartcoach"

def seed_activity_and_splits():
    engine = get_engine(DATABASE_URL)
    session = Session(bind=engine)

    try:
        # ✅ Insert an activity row
        activity = Activity(
            athlete_id=1,
            name="Morning Run",
            type="Run",
            start_date="2024-06-01 07:00:00",
            distance=5000,
            elapsed_time=1500,
            moving_time=1400,
            total_elevation_gain=50,
            external_id="strava-123",
            timezone="America/New_York",
            average_speed=3.5,
            max_speed=4.0
        )
        session.add(activity)
        session.commit()

        print(f"Inserted activity_id: {activity.activity_id}")

        # ✅ Insert a split row tied to activity
        split = Split(
            activity_id=activity.activity_id,
            lap_index=1,
            distance=1000,
            elapsed_time=300,
            moving_time=290,
            average_speed=3.3,
            max_speed=4.0,
            start_index=0,
            end_index=299,
            split=True
        )
        session.add(split)
        session.commit()

        print("✅ Successfully inserted activity and split.")

    except Exception as e:
        print(f"❌ Failed to insert: {e}")
        session.rollback()
    finally:
        session.close()


# ✅ This allows us to call directly for testing
if __name__ == "__main__":
    seed_activity_and_splits()
