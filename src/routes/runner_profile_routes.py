from flask import Blueprint, g, jsonify

from src.db.db_session import get_session
from src.smartcoach_mobile_coach.runner_profile.api_schema import (
    runner_zone_profile_payload,
)
from src.smartcoach_mobile_coach.runner_profile.service import get_runner_profile
from src.utils.auth0_jwt import requires_auth

runner_profile_bp = Blueprint(
    "runner_profile", __name__, url_prefix="/api/runner-profile"
)


@runner_profile_bp.get("/zones")
@requires_auth
def get_runner_profile_zones():
    user_id = getattr(g, "user_id", None)
    if not user_id:
        return jsonify({"status": "error", "message": "No user"}), 401

    session = get_session()
    try:
        profile = get_runner_profile(session, str(user_id))
        return (
            jsonify(
                {"status": "success", "data": runner_zone_profile_payload(profile)}
            ),
            200,
        )
    finally:
        session.close()
