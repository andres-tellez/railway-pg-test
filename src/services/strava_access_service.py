# src/services/strava_access_service.py

import requests
import time

class StravaClient:
    def __init__(self, access_token):
        self.access_token = access_token

    def _request_with_backoff(self, method, url, **kwargs):
        max_retries = 5
        backoff = 10  # Start with 10 sec backoff

        for attempt in range(max_retries):
            response = requests.request(method, url, headers={"Authorization": f"Bearer {self.access_token}"}, **kwargs)

            if response.status_code == 429:
                print(f"⚠️ Rate limit hit (429). Backing off {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2  # Exponential backoff
                continue

            response.raise_for_status()
            return response.json()

        # If we exhausted retries
        raise RuntimeError("Exceeded max retries due to repeated 429 errors")

    def get_activities(self, after=None, before=None, page=1, per_page=200):
        params = {"page": page, "per_page": per_page}
        if after:
            params["after"] = after
        if before:
            params["before"] = before

        url = "https://www.strava.com/api/v3/athlete/activities"
        return self._request_with_backoff("GET", url, params=params)

    def get_activity(self, activity_id):
        url = f"https://www.strava.com/api/v3/activities/{activity_id}"
        return self._request_with_backoff("GET", url)

    def get_hr_zones(self, activity_id):
        url = f"https://www.strava.com/api/v3/activities/{activity_id}/zones"
        try:
            return self._request_with_backoff("GET", url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_splits(self, activity_id):
        url = f"https://www.strava.com/api/v3/activities/{activity_id}/laps"
        try:
            return self._request_with_backoff("GET", url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise
