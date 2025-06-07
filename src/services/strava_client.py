import os
import requests
from datetime import datetime
from src.db.dao.token_dao import get_tokens_sa, save_tokens_sa

class StravaClient:
    def __init__(self, session, athlete_id):
        self.session = session
        self.athlete_id = athlete_id

        token_data = get_tokens_sa(session, athlete_id)
        if not token_data:
            raise RuntimeError(f"No tokens found for athlete_id={athlete_id}")

        self.access_token = token_data["access_token"]
        self.refresh_token = token_data["refresh_token"]
        self.expires_at = token_data["expires_at"]

        if self.is_token_expired():
            self.refresh_access_token()

    def is_token_expired(self):
        now_epoch = int(datetime.utcnow().timestamp())
        return self.expires_at <= now_epoch

    def refresh_access_token(self):
        tokens = StravaClient.refresh_token_static(self.refresh_token)

        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]
        self.expires_at = tokens["expires_at"]

        save_tokens_sa(
            self.session,
            athlete_id=self.athlete_id,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_at=self.expires_at,
        )

    @staticmethod
    def refresh_token_static(refresh_token):
        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")

        response = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def exchange_code_for_token(code):
        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        redirect_uri = os.getenv("REDIRECT_URI")

        response = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()

    def get_activity(self, activity_id):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"https://www.strava.com/api/v3/activities/{activity_id}"

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_hr_zones(self, activity_id):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"https://www.strava.com/api/v3/activities/{activity_id}/zones"

        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_activities(self, after=None, before=None, page=1, per_page=200):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"page": page, "per_page": per_page}
        if after:
            params["after"] = after
        if before:
            params["before"] = before

        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        return response.json()
