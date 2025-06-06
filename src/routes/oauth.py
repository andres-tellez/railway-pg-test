from flask import Blueprint, request, jsonify
import traceback

from src.db.db_session import get_session
from src.db.dao.token_dao import save_tokens_sa
from src.services.activity_sync import sync_full_history
from src.services.strava_client import StravaClient  # ✅ Centralized import

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
            return jsonify(error="Missing `code` param in query string"), 400

        print("🌐 Performing token exchange via centralized StravaClient", flush=True)

        # ✅ Token exchange handled by client
        tokens = StravaClient.exchange_token(code)

        athlete = tokens.get("athlete")
        if not athlete or "id" not in athlete:
            return jsonify(error="Strava response missing athlete ID"), 502

        athlete_id = athlete["id"]
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_at = tokens.get("expires_at")

        if not all([access_token, refresh_token, expires_at]):
            return jsonify(error="Strava response missing required tokens"), 502

        print(f"✅ Got token for athlete {athlete_id}", flush=True)

        session = get_session()
        try:
            save_tokens_sa(
                session,
                athlete_id=athlete_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at
            )

            inserted = sync_full_history(
                session=session,
                athlete_id=athlete_id,
                access_token=access_token,
                lookback_days=730
            )

            print(f"📊 Historical sync inserted {inserted} activities for athlete {athlete_id}", flush=True)
            session.commit()

        except Exception as e:
            session.rollback()
            print("🔥 DB operation failed:", e, flush=True)
            traceback.print_exc()
            return jsonify(error="Database failure", details=str(e)), 500
        finally:
            session.close()

        return jsonify(message="OAuth success!", athlete_id=athlete_id, inserted=inserted), 200

    except Exception as e:
        print("🔥 Internal Error:", str(e), flush=True)
        traceback.print_exc()
        return jsonify(error="Internal Error", details=str(e)), 500
