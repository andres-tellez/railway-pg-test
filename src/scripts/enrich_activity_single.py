import argparse
import os
from sqlalchemy import text
from src.db.db_session import get_session
from src.services.enrichment_sync import enrich_one_activity
from src.services.activity_ingestion import pull_activity_from_strava, insert_activity_into_db

# ------------------------------------------------
parser = argparse.ArgumentParser(description="Ingest + Enrich single Strava activity")
parser.add_argument("--activity-id", type=int, required=True, help="Strava Activity ID")
args = parser.parse_args()
activity_id = args.activity_id

# ------------------------------------------------
admin_access_token = os.getenv("STRAVA_ADMIN_TOKEN")
if not admin_access_token:
    print("❌ STRAVA_ADMIN_TOKEN environment variable is not set. Aborting.")
    exit(1)

session = get_session()

# ------------------------------------------------
# Lookup activity

result = session.execute(
    text("SELECT athlete_id FROM activities WHERE activity_id = :activity_id"),
    {"activity_id": activity_id}
).fetchone()

if result:
    print(f"✅ Activity {activity_id} already exists in DB.")
    athlete_id = result.athlete_id
else:
    print(f"⚠️ Activity {activity_id} not found in DB. Attempting ingestion...")

    activity_json = pull_activity_from_strava(activity_id, admin_access_token)
    athlete_id = insert_activity_into_db(session, activity_json)

# ------------------------------------------------
# Enrichment

print(f"Running enrichment for activity {activity_id}...")
access_token = ensure_fresh_access_token(session, athlete_id)
enrich_one_activity(session, athlete_id, access_token, activity_id)
print("✅ Enrichment completed.")
