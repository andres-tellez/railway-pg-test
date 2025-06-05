import os
import requests

# ✅ Replace this with a real activity ID that you know exists
activity_id = 14663194187  # example from your existing dataset

# ✅ Read access token from environment variable
access_token = os.getenv("STRAVA_ACCESS_TOKEN")

if not access_token:
    raise RuntimeError("Missing STRAVA_ACCESS_TOKEN environment variable")

url = f"https://www.strava.com/api/v3/activities/{activity_id}/zones"
headers = {"Authorization": f"Bearer {access_token}"}

resp = requests.get(url, headers=headers, timeout=10)
print(f"HTTP Status: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    print("✅ Successfully fetched HR zone data:")
    print(data)
else:
    print("❌ Failed to fetch HR zones.")
    print(resp.text)
