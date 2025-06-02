# src/routes/oauth.py

from flask import Blueprint, request, jsonify
import os
import requests

from src.db.db_session import get_session  # ✅ Correct session import
from src.db.dao.token_dao import save_tokens_sa  # ✅ Correct DAO import

oauth_bp = Blueprint("oauth", __name__)

@oauth_bp.route("/oauth/callback")
def oauth_callback():
    try:
        print("📥 /oauth/callback hit", flush=True)
        code = request.args.get("code")
        state = request.args.get("state")
        print("📦 Code received:", code, flush=True)
        print("🆔 State (athlete ID hint):", state, flush=True)

        if not code:
            return "❌ Missing `code` param in query string", 400

        # Read env vars
        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        redirect_uri = os.getenv("REDIRECT_URI")

        print("🌐 Preparing token exchange request", flush=True)

        client_id_int = int(client_id)

        response = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": client_id_int,
                "client_secret": client_secret,
                "code": code,
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

        print(f"✅ Got token for athlete {athlete_id}", flush=True)

        # ✅ Persist tokens using SQLAlchemy DAO
        session = get_session()
        save_tokens_sa(
            session,
            athlete_id=athlete_id,
            access_token=access_token,
            refresh_token=refresh_token
        )

        return f"✅ OAuth success! Token stored for athlete {athlete_id}", 200

    except requests.RequestException as req_err:
        print("❌ RequestException:", str(req_err), flush=True)
        return jsonify(error="Token exchange failed", details=str(req_err)), 502

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Internal Error: {str(e)}", 500
