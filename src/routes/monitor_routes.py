# src/routes/monitor_routes.py

import os
import traceback
from flask import Blueprint, jsonify

from src.db.db_session import get_engine, get_session
from src.services.token_service import get_valid_token  # ✅ Use service layer
from src.db.models.tokens import Token  # ✅ Direct ORM model import

monitor_bp = Blueprint("monitor", __name__)

@monitor_bp.route("/monitor-tokens")
def monitor_tokens():
    try:
        db_url = os.getenv("DATABASE_URL")
        engine = get_engine(db_url)
        session = get_session(engine)
        results = []

        # ✅ Fetch all tokens directly from Token ORM model
        tokens = session.query(Token).all()

        for token in tokens:
            athlete_id = token.athlete_id
            try:
                # ✅ Use fully centralized token refresh logic
                access_token = get_valid_token(session, athlete_id)
                results.append({"athlete_id": athlete_id, "status": "ok", "access_token": access_token})
            except Exception as e:
                results.append({
                    "athlete_id": athlete_id,
                    "status": "error",
                    "error": str(e),
                })

        return jsonify(results=results), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify(error="Monitor failed", details=str(e)), 500
