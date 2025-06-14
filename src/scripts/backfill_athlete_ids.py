from src.db.db_session import get_db_session
from src.db.models.athletes import Athlete
from src.db.models.tokens import Token
from src.db.models.activities import Activity
from src.db.models.splits import Split
from sqlalchemy.orm import Session

def backfill_athletes_and_foreign_keys():
    session: Session = get_db_session()

    try:
        # Step 1: Create missing athletes from tokens
        tokens = session.query(Token).all()
        for token in tokens:
            existing = session.query(Athlete).filter_by(strava_athlete_id=token.strava_athlete_id).first()
            if not existing:
                new_athlete = Athlete(strava_athlete_id=token.strava_athlete_id)
                session.add(new_athlete)
                session.flush()  # get new athlete.id
                token.athlete_id = new_athlete.id
            else:
                token.athlete_id = existing.id

        session.commit()
        print("✅ Athlete table populated and tokens updated.")

        # Step 2: Backfill activities
        for activity in session.query(Activity).all():
            if activity.athlete_id is None:
                token = session.query(Token).filter_by(strava_athlete_id=activity.strava_athlete_id).first()
                if token:
                    activity.athlete_id = token.athlete_id

        session.commit()
        print("✅ Activities updated with athlete_id.")

        # Step 3: Backfill splits
        for split in session.query(Split).all():
            if split.athlete_id is None:
                token = session.query(Token).filter_by(strava_athlete_id=split.strava_athlete_id).first()
                if token:
                    split.athlete_id = token.athlete_id

        session.commit()
        print("✅ Splits updated with athlete_id.")

    except Exception as e:
        session.rollback()
        print("❌ Error during backfill:", e)
    finally:
        session.close()


if __name__ == "__main__":
    backfill_athletes_and_foreign_keys()
