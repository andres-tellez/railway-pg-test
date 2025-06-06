from src.db.db_session import get_session
from src.env_loader import *  # load environment patcher




# TODO: Replace this with a real athlete_id you have authorized via OAuth
athlete_id = 347085


# Create DB session
session = get_session()

try:
    # Step 1: Get valid access token (auto-refresh if needed)
    access_token = ensure_fresh_token(session, athlete_id)

    # Step 2: Run controlled backfill pilot
    synced_count = sync_full_history(
        session=session,
        athlete_id=athlete_id,
        access_token=access_token,
        lookback_days=30,    # ~1 month lookback to yield ~50 activities
        max_activities=50    # hard cap at 50 activities for this pilot run
    )

    print(f"✅ Pilot backfill complete — {synced_count} activities synced for athlete {athlete_id}")

except Exception as e:
    print(f"❌ Backfill pilot failed: {e}")

finally:
    session.close()
