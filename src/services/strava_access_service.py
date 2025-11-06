# services/strava_access_service.py

import requests
import time
import logging
from src.utils.config import config
from src.utils.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class StravaClient:
    def __init__(self, access_token):
        self.access_token = access_token
        self.rate_limiter = get_rate_limiter()

    def _request_with_backoff(self, method, url, **kwargs):
        max_retries = 5
        backoff = 10  # Start with 10 sec backoff

        from src.utils.security_utils import redact_headers, redact_url

        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Redact sensitive data in logs
        redacted_headers = redact_headers(headers)
        redacted_url = redact_url(url) if isinstance(url, str) else url

        logger.debug(f"Strava Request: {method} {redacted_url}")
        logger.debug(f"Headers: {redacted_headers}")
        if "params" in kwargs:
            logger.debug(f"Params: {kwargs['params']}")

        # Check rate limits before making request
        self.rate_limiter.wait_if_needed()

        for attempt in range(max_retries):
            response = requests.request(method, url, headers=headers, **kwargs)

            # Record successful API request (even if it's a 429, we made a request)
            # Only record on first attempt to avoid double-counting
            if attempt == 0:
                self.rate_limiter.record_request()

            if response.status_code == 429:
                print(f"Rate limit hit (429). Backing off {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2
                continue

            if response.status_code == 401:
                from src.utils.security_utils import redact_token

                logger.warning(
                    f"Unauthorized! Token: {redact_token(self.access_token)}"
                )

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

        # Default per_page = min(limit, STRAVA_PER_PAGE) (Strava caps at 200)
        if per_page is None:
            per_page = min(limit, config.STRAVA_PER_PAGE)

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
