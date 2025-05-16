import requests
from src.utils.logger import get_logger

log = get_logger(__name__)


def sync_recent_activities(athlete_id, access_token, per_page=30) -> int:
    """
    Download recent activities from Strava. Returns the number of activities fetched.
    (DB persistence is stubbed out here to avoid import cycles.)
    """
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": per_page}

    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch activities: {resp.status_code} {resp.text}"
        )

    activities = resp.json()
    inserted = 0

    for activity in activities:
        try:
            # If you need to persist here later, do a local import:
            # from src.db import save_tokens_pg  # or your activity‐save fn
            # save_tokens_pg(...)
            inserted += 1

        except Exception as e:
            log.warning(f"Skipping activity {activity.get('id')} due to error: {e}")
            continue

    return inserted
