import os
import requests
from src.db.db_session import get_session
from src.db.dao.token_dao import save_tokens_sa

# Manually paste the code you just got from Strava OAuth
authorization_code = "424e4fcab2763945754ed35ffccd964db28d069c"

# Load your client ID & secret from env (make sure these are set in .env)
client_id = os.getenv("STRAVA_CLIENT_ID")
client_secret = os.getenv("STRAVA_CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")

# Exchange code for tokens
response = requests.post(
    "https://www.strava.com/oauth/token",
    data={
        "client_id": int(client_id),
        "client_secret": client_secret,
        "code": authorization_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    },
    timeout=10,
)

response.raise_for_status()
tokens = response.json()

athlete_id = tokens["athlete"]["id"]
access_token = tokens["access_token"]
refresh_token = tokens["refresh_token"]
expires_at = tokens["expires_at"]

print(f"✅ Got tokens for athlete {athlete_id}")

# Save to DB
session = get_session()
save_tokens_sa(session, athlete_id, access_token, refresh_token, expires_at)
session.close()

print("✅ Tokens saved successfully to DB")
