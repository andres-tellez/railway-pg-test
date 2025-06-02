# src/routes/monitor_routes.py

import os
import traceback
from flask import Blueprint, jsonify

from src.db.db_session import get_engine, get_session  # ✅ Correct imports
from src.db.dao.token_dao import get_tokens_sa, get_valid_access_token_sa  # ✅ Correct DAO imports

monitor_bp = Blueprint("monitor", __name__)

@monitor_bp.route("/monitor-tokens")
def monitor_tokens():
    try:
        db_url = os.getenv("DATABASE_URL")
        engine = get_engine(db_url)
        session = get_session(engine)
        results = []

        # Fetch all token entries using SQLAlchemy
        tokens = session.query(get_tokens_sa.__annotations__.get('return')).all()

        for token in tokens:
            athlete_id = token.athlete_id
            try:
                access_token = get_valid_access_token_sa(session, athlete_id)
                results.append({"athlete_id": athlete_id, "status": "ok" if access_token else "expired"})
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
