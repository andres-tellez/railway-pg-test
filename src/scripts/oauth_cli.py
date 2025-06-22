import os
import time
import webbrowser
import requests
from urllib.parse import urlencode
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()  

from src.db.db_session import get_session
from src.db.models.tokens import Token
from src.db.dao.token_dao import get_tokens_sa

# Load from environment
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI")
AUTH_URL = "https://www.strava.com/oauth/authorize"
STATUS_URL = os.getenv("STRAVA_TOKEN_STATUS_URL")  # Must point to `/auth/token_status?athlete_id=...`

def generate_auth_url():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "approval_prompt": "force",
        "scope": "activity:read_all,profile:read_all"
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def wait_for_token(athlete_id, timeout=120, poll_interval=5):
    print(f"⏳ Waiting for token in DB for athlete {athlete_id}...")
    session = get_session()
    start_time = time.time()
    try:
        while time.time() - start_time < timeout:
            tokens = get_tokens_sa(session, athlete_id)
            if tokens:
                print("✅ Token found in database.")
                return True
            time.sleep(poll_interval)
    finally:
        session.close()
    raise TimeoutError(f"❌ Timed out waiting for token for athlete {athlete_id}")



def authorize_and_wait(athlete_id):
    print(f"➡️ Opening browser for Strava authorization (athlete_id={athlete_id})...")
    webbrowser.open(generate_auth_url())

    if not wait_for_token(athlete_id):
        raise RuntimeError("❌ Token not received after authorization.")

    print(f"🎯 OAuth flow completed for athlete {athlete_id}")

# Reusable entrypoint for programmatic use
def main(athlete_id_override=None):
    athlete_id = athlete_id_override or int(input("Enter athlete_id: "))
    authorize_and_wait(athlete_id)

# Only used for manual testing
if __name__ == "__main__":
    main()
