#!/usr/bin/env python3
"""
Debug script to check Auth0 configuration.
Run this to verify that Auth0 environment variables are set correctly.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("Auth0 Configuration Check")
print("=" * 60)

config_vars = [
    "AUTH0_DOMAIN",
    "AUTH0_AUDIENCE",
    "AUTH0_ISSUER",
]

for var in config_vars:
    value = os.getenv(var)
    if value:
        print(f"✅ {var}: {value}")
    else:
        print(f"❌ {var}: NOT SET")

print("=" * 60)
print("Checking JWKS endpoint...")
domain = os.getenv("AUTH0_DOMAIN")
if domain:
    jwks_url = f"https://{domain}/.well-known/jwks.json"
    print(f"JWKS URL: {jwks_url}")

    # Try to fetch JWKS
    import requests

    try:
        response = requests.get(jwks_url, timeout=5)
        if response.status_code == 200:
            print("✅ JWKS endpoint is accessible")
        else:
            print(f"❌ JWKS endpoint returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to fetch JWKS: {e}")
else:
    print("❌ Cannot check JWKS - AUTH0_DOMAIN not set")

print("=" * 60)
