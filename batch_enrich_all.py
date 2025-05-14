import requests
import time

ATHLETE_ID = 347085
KEY = "YOUR_REAL_CRON_KEY"
BASE_URL = "http://127.0.0.1:5000/enrich-activities"
LIMIT = 25
OFFSET = 0
STOP_IF_EMPTY = True

while True:
    url = f"{BASE_URL}/{ATHLETE_ID}?key={KEY}&offset={OFFSET}&limit={LIMIT}"
    print(f"🔁 Requesting: offset={OFFSET}, limit={LIMIT}")
    
    try:
        resp = requests.get(url)
    except Exception as e:
        print(f"❌ Network error: {e}")
        time.sleep(60)
        continue

    if resp.status_code == 429:
        print("⏳ Rate limit hit. Sleeping for 10 minutes...")
        time.sleep(600)
        continue

    if resp.status_code != 200:
        print(f"⚠️ Unexpected status code {resp.status_code}. Sleeping 1 min...")
        time.sleep(60)
        continue

    data = resp.json()
    enriched = data.get("enriched", 0)
    print(f"✅ Enriched: {enriched} activities")

    if enriched == 0 and STOP_IF_EMPTY:
        print("🎉 All done.")
        break

    OFFSET += LIMIT
    time.sleep(3)
