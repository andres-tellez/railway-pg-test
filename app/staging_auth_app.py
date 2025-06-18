# staging_auth_app.py

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from flask import Flask, redirect, request, jsonify
from src.services.token_service import get_authorization_url, store_tokens_from_callback
from src.db.db_session import get_session

app = Flask(__name__)

@app.route("/auth/login")
def strava_login():
    """
    Redirect to Strava OAuth URL (called manually from browser)
    """
    return redirect(get_authorization_url())


@app.route("/auth/callback")
def strava_callback():
    """
    Handle OAuth redirect from Strava, exchange code, and persist tokens.
    """
    session = get_session()
    try:
        code = request.args.get("code")
        if not code:
            return "Missing OAuth code", 400

        athlete_id = store_tokens_from_callback(code, session)
        return jsonify({
            "status": "✅ Token stored",
            "athlete_id": athlete_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/ping")
def ping():
    return "pong from staging OAuth app"


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8888))
    app.run(host="0.0.0.0", port=port)
