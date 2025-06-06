import requests
import time
import logging
import os
from src.db.db_session import get_session
from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa

class StravaClient:
    BASE_URL = "https://www.strava.com/api/v3"
    RETRY_LIMIT = 5
    BACKOFF_FACTOR = 2
    INITIAL_BACKOFF = 1  # seconds

    def __init__(self, athlete_id: int):
        self.athlete_id = athlete_id
        self.logger = logging.getLogger("StravaClient")
        self.session = get_session()
        self.access_token = self._ensure_valid_access_token()

    def _ensure_valid_access_token(self):
        tokens = get_tokens_sa(self.session, self.athlete_id)
        if not tokens:
            raise RuntimeError(f"No tokens found for athlete {self.athlete_id}")

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        now_ts = int(time.time())
        token_row = self.session.execute(
            f"SELECT expires_at FROM tokens WHERE athlete_id = {self.athlete_id}"
        ).fetchone()

        if token_row and token_row.expires_at > now_ts:
            return access_token

        self.logger.info(f"Access token expired for athlete {self.athlete_id}, refreshing...")

        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")

        response = requests.post(
            f"{self.BASE_URL}/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            },
            timeout=10,
        )

        response.raise_for_status()
        new_tokens = response.json()

        new_access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens["refresh_token"]
        new_expires_at = new_tokens["expires_at"]

        save_tokens_sa(
            self.session,
            athlete_id=self.athlete_id,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_at=new_expires_at
        )

        return new_access_token

    def _request(self, method, endpoint, params=None, data=None, json=None, timeout=10):
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        backoff = self.INITIAL_BACKOFF

        for attempt in range(1, self.RETRY_LIMIT + 1):
            try:
                resp = requests.request(
                    method, url, headers=headers, params=params,
                    data=data, json=json, timeout=timeout
                )

                if resp.status_code == 401 and attempt == 1:
                    self.logger.warning("Unauthorized, refreshing token and retrying once...")
                    self.access_token = self._ensure_valid_access_token()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    continue

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", backoff))
                    self.logger.warning(f"Rate limit hit. Sleeping {retry_after}s (Attempt {attempt})")
                    time.sleep(retry_after)
                    continue

                elif resp.status_code >= 500:
                    self.logger.warning(f"Server error {resp.status_code}. Retrying in {backoff}s (Attempt {attempt})")
                    time.sleep(backoff)
                    backoff *= self.BACKOFF_FACTOR
                    continue

                elif resp.status_code >= 400:
                    self.logger.error(f"Client error {resp.status_code}: {resp.text}")
                    resp.raise_for_status()

                return resp.json()

            except requests.RequestException as e:
                self.logger.error(f"Request failed: {e}")
                time.sleep(backoff)
                backoff *= self.BACKOFF_FACTOR

        raise RuntimeError(f"Strava API request failed after {self.RETRY_LIMIT} attempts")

    def get_activity(self, activity_id: int, include_all_efforts: bool = True):
        params = {"include_all_efforts": str(include_all_efforts).lower()}
        return self._request("GET", f"activities/{activity_id}", params=params)

    def list_activities(self, after_timestamp: int, page: int = 1, per_page: int = 100):
        params = {"after": after_timestamp, "page": page, "per_page": per_page}
        return self._request("GET", "athlete/activities", params=params)

    def get_zones(self, activity_id: int):
        return self._request("GET", f"activities/{activity_id}/zones")

    @staticmethod
    def exchange_token(code: str):
        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        redirect_uri = os.getenv("REDIRECT_URI")

        url = "https://www.strava.com/api/v3/oauth/token"
        data = {
            "client_id": int(client_id),
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        }
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()
        return resp.json()
