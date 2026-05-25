from flask import Blueprint, g, jsonify

from src.db.dao.plans_dao import get_active_or_most_recent_plan
from src.db.db_session import get_session
from src.smartcoach_mobile_coach.runner_profile.api_schema import (
    runner_zone_profile_payload,
)
from src.smartcoach_mobile_coach.runner_profile.service import (
    get_runner_profile,
    get_runner_training_pace_recommendations,
)
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
        plan_row = get_active_or_most_recent_plan(session, str(user_id))
        target_time = plan_row.target_time if plan_row is not None else None
        training_pace_recommendations = get_runner_training_pace_recommendations(
            session,
            str(user_id),
            target_time=target_time,
            plan=plan_row,
            profile=profile,
        )
        return (
            jsonify(
                {
                    "status": "success",
                    "data": runner_zone_profile_payload(
                        profile,
                        training_pace_recommendations=training_pace_recommendations,
                    ),
                }
            ),
            200,
        )
    finally:
        session.close()
