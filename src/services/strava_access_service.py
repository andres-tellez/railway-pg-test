"""
Strava API Access Service
=========================

This module provides a client for making authenticated requests to the Strava API.

The StravaClient class handles:
- Authenticated API requests with Bearer tokens
- Rate limiting to respect Strava API limits
- Automatic retry with exponential backoff on 429 (rate limit) errors
- Token redaction in logs for security
- Stream data conversion and normalization

Key Features:
- Rate Limiting: Automatically respects Strava's rate limits (600 requests per 15 minutes)
- Retry Logic: Automatically retries on 429 errors with exponential backoff
- Security: Redacts sensitive tokens from logs
- Error Handling: Provides clear error messages for API failures

Usage:
    from src.services.strava_access_service import StravaClient

    client = StravaClient(access_token="your_token")
    activities = client.get_activities(per_page=30)
    activity = client.get_activity(activity_id=123456)
    streams = client.get_streams(activity_id=123456, types=["time", "distance"])

API Endpoints Used:
- GET /athlete/activities - List athlete activities
- GET /activities/{id} - Get activity details
- GET /activities/{id}/streams - Get activity streams (time, distance, etc.)

Rate Limits:
- Strava API: 600 requests per 15 minutes per application
- This client automatically enforces these limits

References:
- https://developers.strava.com/docs/reference/
- https://developers.strava.com/docs/rate-limits/
"""

import requests
import time
import logging
from src.utils.config import config
from src.utils.rate_limiter import get_rate_limiter
from src.utils.strava_exceptions import (
    StravaAPIError,
    StravaRateLimitError,
    StravaAuthenticationError,
)

logger = logging.getLogger(__name__)


class StravaClient:
    def __init__(self, access_token):
        self.access_token = access_token
        self.rate_limiter = get_rate_limiter()

    def _request_with_backoff(self, method, url, **kwargs):
        max_retries = config.STRAVA_MAX_RETRIES
        backoff = config.STRAVA_INITIAL_BACKOFF  # Start with configured backoff

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
                retry_after = int(response.headers.get("Retry-After", backoff))
                logger.warning(
                    f"Rate limit hit (429). Backing off {backoff} seconds... "
                    f"(Retry-After: {retry_after}s)"
                )
                time.sleep(backoff)
                backoff *= 2
                continue

            if response.status_code == 401:
                from src.utils.security_utils import redact_token

                logger.warning(
                    f"Unauthorized! Token: {redact_token(self.access_token)}"
                )
                raise StravaAuthenticationError(
                    "Strava API authentication failed",
                    details={
                        "url": redact_url(url),
                        "method": method,
                        "attempt": attempt + 1,
                    },
                )

            try:
                response.raise_for_status()
                self._record_rate_headers(response.headers)
                return response.json()
            except requests.exceptions.HTTPError as e:
                # Convert HTTP errors to StravaAPIError
                raise StravaAPIError(
                    f"Strava API request failed: {e}",
                    status_code=response.status_code,
                    response_body=response.text[:500] if response.text else None,
                    details={
                        "url": redact_url(url),
                        "method": method,
                        "attempt": attempt + 1,
                    },
                )

        # Exceeded max retries
        raise StravaRateLimitError(
            f"Exceeded max retries ({max_retries}) due to repeated 429 errors",
            retry_after=backoff,
            details={
                "url": redact_url(url),
                "method": method,
                "max_retries": max_retries,
            },
        )

    def get_activities(self, after=None, before=None, limit=None, per_page=None):
        """
        Fetch activities from Strava for the authenticated athlete.

        Args:
            after (int | None): Unix timestamp (seconds) - only return activities after this time.
            before (int | None): Unix timestamp (seconds) - only return activities before this time.
            limit (int | None): Optional cap on total activities to fetch.
            per_page (int | None): How many activities to fetch per API page. Defaults to 200.

        Returns:
            list[dict]: A list of Strava activity objects.
        """
        url = f"{config.STRAVA_API_BASE_URL}/athlete/activities"
        all_activities = []
        page = 1

        # Default limit from config if not provided
        if per_page is None:
            per_page = config.STRAVA_PER_PAGE

        while True:
            remaining = None
            if limit is not None:
                remaining = limit - len(all_activities)
                if remaining <= 0:
                    break

            params = {
                "page": page,
                "per_page": (
                    min(per_page, remaining) if remaining is not None else per_page
                ),
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
            if limit is not None and len(all_activities) >= limit:
                return all_activities[:limit]

            page += 1

        return all_activities

    def get_activities_page(
        self,
        *,
        page: int = 1,
        per_page: int | None = None,
        after: int | None = None,
        before: int | None = None,
    ) -> list[dict]:
        """Fetch a single page of activities from Strava."""
        url = f"{config.STRAVA_API_BASE_URL}/athlete/activities"
        params = {
            "page": page,
            "per_page": per_page or config.STRAVA_PER_PAGE,
        }
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        return self._request_with_backoff("GET", url, params=params)

    def get_activity(self, activity_id):
        url = f"{config.STRAVA_API_BASE_URL}/activities/{activity_id}"
        return self._request_with_backoff("GET", url)

    def get_athlete(self):
        """Get authenticated athlete's profile including max_heartrate."""
        url = f"{config.STRAVA_API_BASE_URL}/athlete"
        return self._request_with_backoff("GET", url)

    def get_hr_zones(self, activity_id):
        url = f"{config.STRAVA_API_BASE_URL}/activities/{activity_id}/zones"
        try:
            return self._request_with_backoff("GET", url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except StravaAPIError as e:
            # Handle 402 Payment Required (user may not have Strava Summit or API access issue)
            # Also handle 404 if it comes through as StravaAPIError
            if e.status_code == 402:
                logger.warning(
                    f"HR zones unavailable for activity {activity_id} "
                    f"(402 Payment Required - may be subscription or API access issue)"
                )
                return None
            if e.status_code == 404:
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
                    logger.warning(f"Failed to convert stream {key}: {e}")
                    streams[key] = []
            else:
                streams[key] = []
        return streams

    def _record_rate_headers(self, headers):
        """
        Record Strava rate limit headers for diagnostics.
        """
        try:
            limit_header = headers.get("X-RateLimit-Limit")
            usage_header = headers.get("X-RateLimit-Usage")
            if not limit_header or not usage_header:
                return

            limits = [int(x) for x in limit_header.split(",")]
            usage = [int(x) for x in usage_header.split(",")]
            if len(limits) != 2 or len(usage) != 2:
                return

            short_limit, long_limit = limits
            short_usage, long_usage = usage

            logger.debug(
                "Strava rate headers – short: %d/%d, long: %d/%d",
                short_usage,
                short_limit,
                long_usage,
                long_limit,
            )

            from src.utils.rate_limiter import get_rate_limiter

            limiter = get_rate_limiter()
            limiter.update_strava_headers(
                short_usage, short_limit, long_usage, long_limit
            )
        except Exception as exc:  # pragma: no cover
            logger.debug(f"Failed to record Strava rate headers: {exc}")
