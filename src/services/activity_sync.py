# src/services/activity_sync.py

import requests
from src.utils.logger import get_logger

log = get_logger(__name__)


def sync_recent_activities(athlete_id, access_token, per_page=30) -> int:
    """
    Download recent activities from Strava. Returns the number of activities fetched.
    (DB persistence is stubbed out for now to avoid circular imports.)
    """
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": per_page}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch activities: {response.status_code} {response.text}"
        )

    activities = response.json()
    inserted = 0

    for activity in activities:
        try:
            # TODO: Persist this activity to the database.
            # If you need to save tokens inside here (unlikely), defer the import:
            # from src.db import save_tokens_pg
            # save_tokens_pg(athlete_id, new_access_token, new_refresh_token)
            #
            # For now, we just count them:
            inserted += 1

        except Exception as e:
            log.warning(f"Skipping activity {activity.get('id')} due to error: {e}")
            continue

    return inserted
