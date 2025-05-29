# src/services/strava.py

import requests
from datetime import datetime

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

def fetch_activities_between(access_token, start_date, end_date, per_page=200):
    """
    Fetch all Strava activities for an athlete within a date range.
    Handles pagination. Raises RuntimeError on 401.
    """
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "after": int(start_date.timestamp()),
        "before": int(end_date.timestamp()),
        "per_page": per_page,
    }

    all_activities = []
    page = 1

    while True:
        params["page"] = page
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 401:
            print("❌ 401 Unauthorized – Strava rejected the token.")
            print("🔐 Access token used:", access_token)
            print("📝 Response body:", response.text)
            raise RuntimeError("Access token unauthorized or expired.")

        elif response.status_code != 200:
            print(f"❌ Unexpected Strava error {response.status_code}")
            print("📝 Response body:", response.text)
            raise RuntimeError(f"Strava API error {response.status_code}")

        batch = response.json()
        if not batch:
            break

        all_activities.extend(batch)
        page += 1

    return all_activities
