#!/usr/bin/env python3
"""Test webhook by sending a fake webhook event to the API"""

import requests
import json

# Your Railway backend URL
WEBHOOK_URL = "https://api.smartcoach.dev/webhooks/strava"

# Simulate a Strava webhook event payload
test_payload = {
    "aspect_type": "create",
    "event_time": 1760374604,
    "object_id": 12345678901,  # Large ID to test BigInteger
    "object_type": "activity",
    "owner_id": 347085,  # Your athlete ID
    "subscription_id": 309430,
    "updates": {}
}

print("🧪 Testing webhook endpoint...")
print(f"📤 Sending POST to: {WEBHOOK_URL}")
print(f"📦 Payload: {json.dumps(test_payload, indent=2)}")

try:
    response = requests.post(
        WEBHOOK_URL,
        json=test_payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\n📥 Response Status: {response.status_code}")
    print(f"📥 Response Body: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! Webhook accepted")
        print("\nNow check Railway logs to see if the event was stored without errors")
    else:
        print(f"\n❌ FAILED with status {response.status_code}")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")

