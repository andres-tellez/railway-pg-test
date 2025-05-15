# src/services/strava.py

def enrich_activity(activity_id, key=None):
    """
    Stub for enriching a single Strava activity.
    Accepts activity ID and optional secret key; returns enrichment result dict.
    """
    raise NotImplementedError("enrich_activity not implemented")

def backfill_activities(since=None):
    """
    Stub for backfilling multiple activities since a given date.
    Returns count of activities processed.
    """
    raise NotImplementedError("backfill_activities not implemented")
