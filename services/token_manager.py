import os
import requests

API_BASE = "https://www.strava.com/api/v3"

def exchange_code_for_tokens(code, client_id, client_secret):
    resp = requests.post(f"{API_BASE}/oauth/token", data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "code":          code,
        "grant_type":    "authorization_code"
    })
    if resp.status_code != 200:
        return {
            "error":   "exchange_failed",
            "details": resp.text,
            "status":  resp.status_code
        }

    data = resp.json()
    return {
        "athlete_id":    data["athlete"]["id"],
        "access_token":  data["access_token"],
        "refresh_token": data["refresh_token"]
    }

def refresh_access_token(athlete_id, refresh_token, client_id, client_secret):
    resp = requests.post(f"{API_BASE}/oauth/token", data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token
    })
    if resp.status_code != 200:
        return None
    return resp.json().get("access_token")
