# src/routes/monitor_routes.py

import os
import traceback
from flask import Blueprint, jsonify
from src.core import get_engine, get_session
from src.db.dao.token_dao import get_tokens_sa
from src.routes.sync_routes import get_valid_access_token

monitor_bp = Blueprint("monitor", __name__)

@monitor_bp.route("/monitor-tokens")
def monitor_tokens():
    try:
        engine = get_engine(os.getenv("DATABASE_URL"))
        session = get_session(engine)
        results = []

        # Fetch all token entries
        token_model = get_tokens_sa.__self__.model if hasattr(get_tokens_sa, '__self__') else None
        if token_model is None:
            raise RuntimeError("get_tokens_sa does not expose model attribute")

        all_tokens = session.query(token_model).all()

        for t in all_tokens:
            athlete_id = t.athlete_id
            try:
                token = get_valid_access_token(athlete_id)
                results.append({"athlete_id": athlete_id, "status": "ok"})
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
