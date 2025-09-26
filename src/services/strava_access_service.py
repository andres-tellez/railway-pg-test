# services/strava_access_service.py

import requests
import time
from src.utils.config import config


class StravaClient:
    def __init__(self, access_token):
        self.access_token = access_token

    def _request_with_backoff(self, method, url, **kwargs):
        max_retries = 5
        backoff = 10  # Start with 10 sec backoff

        headers = {"Authorization": f"Bearer {self.access_token}"}

        print(f"📤 Strava Request: {method} {url}")
        print(f"📤 Headers: {headers}")
        if "params" in kwargs:
            print(f"📤 Params: {kwargs['params']}")

        for attempt in range(max_retries):
            response = requests.request(method, url, headers=headers, **kwargs)

            if response.status_code == 429:
                print(f"⚠️ Rate limit hit (429). Backing off {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2
                continue

            if response.status_code == 401:
                print(f"❌ Unauthorized! Token: {self.access_token}")

            response.raise_for_status()
            return response.json()

        raise RuntimeError("Exceeded max retries due to repeated 429 errors")

    def get_activities(self, after=None, before=None, limit=None, per_page=None):
        """
        Fetch activities from Strava for the authenticated athlete.

        Args:
            after (int | None): Unix timestamp (seconds) - only return activities after this time.
            before (int | None): Unix timestamp (seconds) - only return activities before this time.
            limit (int | None): Maximum number of activities to fetch. Defaults to config.MAX_ACTIVITIES_TO_DOWNLOAD.
            per_page (int | None): How many activities to fetch per API page. Defaults to min(limit, 200).

        Returns:
            list[dict]: A list of Strava activity objects.
        """
        url = f"{config.STRAVA_API_BASE_URL}/athlete/activities"
        all_activities = []
        page = 1

        # Default limit from config if not provided
        if limit is None:
            limit = config.MAX_ACTIVITIES_TO_DOWNLOAD

        # Default per_page = min(limit, 200) (Strava caps at 200)
        if per_page is None:
            per_page = min(limit, 200)

        while len(all_activities) < limit:
            params = {
                "page": page,
                "per_page": min(
                    per_page, limit - len(all_activities)
                ),  # don’t overshoot limit
            }
            if after:
                params["after"] = after
            if before:
                params["before"] = before

            batch = self._request_with_backoff("GET", url, params=params)

            if not batch:
                break

            all_activities.extend(batch)

            # Stop early if we've hit the limit
            if len(all_activities) >= limit:
                return all_activities[:limit]

            page += 1

        return all_activities

    def get_activity(self, activity_id):
        url = f"{config.STRAVA_API_BASE_URL}/activities/{activity_id}"
        return self._request_with_backoff("GET", url)

    def get_hr_zones(self, activity_id):
        url = f"{config.STRAVA_API_BASE_URL}/activities/{activity_id}/zones"
        try:
            return self._request_with_backoff("GET", url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_splits(self, activity_id):
        url = f"{config.STRAVA_API_BASE_URL}/activities/{activity_id}/laps"
        try:
            return self._request_with_backoff("GET", url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise

    def get_streams(self, activity_id, keys):
        url = f"{config.STRAVA_API_BASE_URL}/activities/{activity_id}/streams"
        resp = self._request_with_backoff(
            "GET", url, params={"keys": ",".join(keys), "key_by_type": "true"}
        )

        streams = {}
        for key in keys:
            raw = resp.get(key)
            if isinstance(raw, dict) and "data" in raw:
                try:
                    streams[key] = [
                        float(x)
                        for x in raw["data"]
                        if isinstance(x, (int, float, str))
                        and str(x).replace(".", "", 1).isdigit()
                    ]
                except Exception as e:
                    print(f"Failed to convert stream {key}: {e}")
                    streams[key] = []
            else:
                streams[key] = []
        return streams
