# src/platform/strava.py

def enrich_activity(activity_id):
    return {"status": "enriched", "activity_id": activity_id}

def backfill_activities(athlete_id):
    return {"status": "backfilled", "athlete_id": athlete_id}
