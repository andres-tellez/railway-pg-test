from flask import Blueprint, jsonify, g
from src.utils.auth import requires_auth
import threading

bp = Blueprint("progress", __name__)

# ✅ In-memory progress store – keyed by user_id (UUID)
_progress_state = {}
_lock = threading.Lock()

# ✅ normalization map (backend stages -> UI stages)
NORMALIZE = {
    "starting": "starting",
    "auth_ok": "fetching",
    "compute_window": "fetching",
    "fetch_start": "fetching",
    "fetch_done": "fetching",
    "filter_done": "fetching",
    "upsert_start": "enriching",
    "upsert_done": "enriching",
    "enrich_start": "enriching",
    "enrich_done": "enriching",
    "done": "done",
    "error": "error",
}


@bp.route("/api/progress/status")
@requires_auth
def get_progress_status():
    """
    Returns progress state for the current user (by user_id).
    Authenticated via JWT.
    """
    user_id = g.user["internal_id"]

    with _lock:
        state = _progress_state.get(
            str(user_id),
            {
                "stage": "starting",
                "message": "Waiting to start…",
                "percent": 0,
            },
        )

    # ✅ Add normalized stage for frontend
    normalized = NORMALIZE.get(state.get("stage", "starting"), "starting")
    state_with_ui = {**state, "ui_stage": normalized}

    return jsonify(state_with_ui)


def set_progress(user_id: str, stage: str, message: str, percent: float):
    """
    Called by ingestion_orchestrator_service to update progress for the given user_id.
    """
    with _lock:
        _progress_state[str(user_id)] = {
            "stage": stage,
            "message": message,
            "percent": percent,
        }
