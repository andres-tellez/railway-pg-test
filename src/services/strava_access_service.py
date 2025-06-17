import requests
import time

from src.utils.config import STRAVA_API_BASE_URL


class StravaClient:
    def __init__(self, access_token):
        self.access_token = access_token

    def _request_with_backoff(self, method, url, **kwargs):
        max_retries = 5
        backoff = 10  # Start with 10 sec backoff

        for attempt in range(max_retries):
            response = requests.request(
                method,
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                **kwargs
            )

            if response.status_code == 429:
                print(f"⚠️ Rate limit hit (429). Backing off {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2
                continue

            response.raise_for_status()
            return response.json()

        raise RuntimeError("Exceeded max retries due to repeated 429 errors")

    def get_activities(self, after=None, before=None, max_items=None, per_page=200):
        url = f"{STRAVA_API_BASE_URL}/athlete/activities"
        all_activities = []
        page = 1

        while True:
            params = {
                "page": page,
                "per_page": per_page
            }
            if after:
                params["after"] = after
            if before:
                params["before"] = before

            batch = self._request_with_backoff("GET", url, params=params)

            if not batch:
                break

            all_activities.extend(batch)

            if max_items and len(all_activities) >= max_items:
                return all_activities[:max_items]

            page += 1

        return all_activities

    def get_activity(self, activity_id):
        url = f"{STRAVA_API_BASE_URL}/activities/{activity_id}"
        return self._request_with_backoff("GET", url)

    def get_hr_zones(self, activity_id):
        url = f"{STRAVA_API_BASE_URL}/activities/{activity_id}/zones"
        try:
            return self._request_with_backoff("GET", url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_splits(self, activity_id):
        url = f"{STRAVA_API_BASE_URL}/activities/{activity_id}/laps"
        try:
            return self._request_with_backoff("GET", url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise

    def get_streams(self, activity_id, keys):
        url = f"{STRAVA_API_BASE_URL}/activities/{activity_id}/streams"
        resp = self._request_with_backoff("GET", url, params={"keys": ",".join(keys), "key_by_type": "true"})

        streams = {}
        for key in keys:
            raw = resp.get(key)
            if isinstance(raw, dict) and "data" in raw:
                try:
                    streams[key] = [float(x) for x in raw["data"] if isinstance(x, (int, float, str)) and str(x).replace('.', '', 1).isdigit()]
                except Exception as e:
                    print(f"Failed to convert stream {key}: {e}")
                    streams[key] = []
            else:
                streams[key] = []
        return streams
