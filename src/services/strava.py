import os
import time
import requests
from datetime import datetime
from urllib.parse import urlencode
from src.db.dao.token_dao import get_token_pg, save_tokens_pg


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


def get_valid_access_token(athlete_id):
    """
    Retrieve a valid access token for the athlete.
    If expired, refresh it using the refresh token and update the DB.
    """
    tokens = get_token_pg(athlete_id)
    if not tokens:
        raise Exception(f"No tokens found for athlete {athlete_id}")

    if tokens["expires_at"] < time.time():
        resp = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": os.getenv("STRAVA_CLIENT_ID"),
                "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
            },
        )
        resp.raise_for_status()
        new_tokens = resp.json()
        save_tokens_pg(athlete_id, new_tokens)
        return new_tokens["access_token"]

    return tokens["access_token"]


def generate_strava_auth_url(athlete_id=None):
    """
    Generate an authorization URL for Strava OAuth with optional state.
    """
    client_id = os.getenv("STRAVA_CLIENT_ID")
    redirect_uri = os.getenv("REDIRECT_URI")  # ✅ Fixed env var name to match .env
    if not redirect_uri:
        raise RuntimeError("Missing REDIRECT_URI in environment.")

    scope = "read,activity:read_all"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": scope,
    }
    if athlete_id:
        params["state"] = str(athlete_id)

    return f"https://www.strava.com/oauth/authorize?{urlencode(params)}"
