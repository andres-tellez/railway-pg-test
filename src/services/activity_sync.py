# services/activity_sync.py

import requests
from db import save_activity_pg
from src.utils.logger import get_logger

log = get_logger(__name__)


def sync_recent_activities(athlete_id, access_token, max=30) -> int:
    """
    Download recent activities from Strava and insert them into the DB.
    Returns number of activities inserted.
    """
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": max}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch activities: {response.status_code} {response.text}"
        )

    activities = response.json()
    inserted = 0
    for activity in activities:
        try:
            save_activity_pg(activity)
            inserted += 1
        except Exception as e:
            print(f"⚠️ Skipping activity {activity.get('id')} due to error: {e}")
            continue

    return inserted
