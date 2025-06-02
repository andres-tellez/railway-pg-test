# src/routes/oauth.py

from flask import Blueprint, request, jsonify
import os
import requests
import traceback

from src.db.db_session import get_session
from src.db.dao.token_dao import save_tokens_sa
from src.services.activity_sync import sync_full_history  # ✅ Unified ingestion import

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
        expires_at = tokens["expires_at"]  # ✅ NEW LINE: read expiry from Strava

        print(f"✅ Got token for athlete {athlete_id}", flush=True)

        # ✅ Persist tokens using SQLAlchemy DAO
        session = get_session()
        try:
            save_tokens_sa(
                session,
                athlete_id=athlete_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at  # ✅ PASS EXPIRES_AT INTO DAO
            )

            # ✅ Immediately trigger historical ingestion
            inserted = sync_full_history(session, athlete_id, access_token)
            print(f"📊 Historical sync inserted {inserted} activities for athlete {athlete_id}", flush=True)

            session.commit()

        except Exception as e:
            session.rollback()
            print("🔥 DB operation failed:", e, flush=True)
            traceback.print_exc()
            return f"❌ DB failure: {str(e)}", 500
        finally:
            session.close()

        return f"✅ OAuth success! Token stored and historical sync completed for athlete {athlete_id}", 200

    except requests.RequestException as req_err:
        print("❌ RequestException:", str(req_err), flush=True)
        return jsonify(error="Token exchange failed", details=str(req_err)), 502

    except Exception as e:
        print("🔥 Internal Error:", str(e), flush=True)
        traceback.print_exc()
        return f"❌ Internal Error: {str(e)}", 500
