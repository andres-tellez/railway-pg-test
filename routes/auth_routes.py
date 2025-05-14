from flask import Blueprint, jsonify, redirect, request
import os
import requests
from services.token_manager import exchange_code_for_tokens
from db import save_token_pg

AUTH = Blueprint("auth", __name__)
CLIENT_ID     = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("REDIRECT_URI", "http://127.0.0.1:5000/oauth/callback")

@AUTH.route("/connect-strava")
def connect_strava():
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": "activity:read,activity:write"
    }
    url = f"https://www.strava.com/oauth/authorize?{requests.compat.urlencode(params)}"
    return redirect(url)

@AUTH.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return jsonify(error="Missing code"), 400

    result = exchange_code_for_tokens(code, CLIENT_ID, CLIENT_SECRET)
    if result.get("error"):
        return jsonify(error=result["error"], details=result.get("details")), result.get("status", 400)

    athlete_id    = result["athlete_id"]
    access_token  = result["access_token"]
    refresh_token = result["refresh_token"]

    save_token_pg(athlete_id, access_token, refresh_token)
    return jsonify(
        athlete_id    = athlete_id,
        access_token  = access_token,
        refresh_token = refresh_token
    ), 200
