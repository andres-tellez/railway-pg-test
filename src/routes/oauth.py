from flask import Blueprint, request, jsonify
import os
import requests
from src.db.dao.token_dao import save_tokens_pg  # Updated import

oauth_bp = Blueprint("oauth", __name__)

@oauth_bp.route("/oauth/callback")
def oauth_callback():
    try:
        print("📥 /oauth/callback hit", flush=True)
        code = request.args.get("code")
        state = request.args.get("state")  # Optional athlete ID passed earlier
        print("📦 Code received:", code, flush=True)
        print("🆔 State (athlete ID hint):", state, flush=True)

        if not code:
            return "❌ Missing `code` param in query string", 400

        # Exchange code for tokens
        response = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": os.getenv("STRAVA_CLIENT_ID"),
                "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )

        response.raise_for_status()
        tokens = response.json()

        athlete_id = tokens["athlete"]["id"]
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expires_at = tokens["expires_at"]

        print(f"✅ Got token for athlete {athlete_id}", flush=True)

        # Persist to DB
        save_tokens_pg(
            athlete_id=athlete_id,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        return f"✅ OAuth success! Token stored for athlete {athlete_id}", 200

    except requests.RequestException as req_err:
        return jsonify(error="Token exchange failed", details=str(req_err)), 502
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Internal Error: {str(e)}", 500
