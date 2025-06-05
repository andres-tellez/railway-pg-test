# src/scripts/test_single_enrichment.py

import os
import requests

# Hardcode the activity id we want to test
activity_id = 14663194187

# Paste your valid access token here:
access_token = "f0a988311cc64557330577b7a9c461097941b1c2"

url = f"https://www.strava.com/api/v3/activities/{activity_id}/zones"
headers = {"Authorization": f"Bearer {access_token}"}

response = requests.get(url, headers=headers, timeout=10)

print(f"HTTP Status: {response.status_code}")
if response.status_code != 200:
    print("❌ Failed to fetch HR zones.")
    print(response.text)
else:
    zones_data = response.json()
    print("✅ Successfully fetched HR zone data:")
    print(zones_data)
    
    # Optional: extract HR zones cleanly
    for zone_group in zones_data:
        if zone_group.get("type") == "heartrate":
            hr_zones = zone_group.get("zones", [])
            total_time = sum(z.get("time", 0) for z in hr_zones)
            print(f"Total HR recorded time: {total_time} sec")
            for i, z in enumerate(hr_zones):
                pct = round((z.get("time", 0) / total_time) * 100, 1) if total_time > 0 else 0
                print(f"Zone {i+1}: {pct}%")
