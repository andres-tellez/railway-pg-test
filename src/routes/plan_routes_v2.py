"""
Plan Routes V2 - Refactored deterministic draft plan endpoint
"""

from flask import Blueprint, jsonify, request, g
import logging

from src.db.db_session import get_session
from src.schemas.plan_schema import PlanCreateSchema
from src.utils.auth0_jwt import requires_auth
from src.utils.timezone_helpers import resolve_timezone
from src.routes.plan_generation_v2 import (
    run_v2_plan_generation,
    build_standard_draft_payload,
)

logger = logging.getLogger(__name__)

plan_bp_v2 = Blueprint("plan_v2", __name__, url_prefix="/api/plan-v2")


@plan_bp_v2.route("/draft", methods=["POST"])
@requires_auth
def create_plan_draft_v2():
    """Generate a draft plan using the refactored v2 pipeline."""
    user_id = getattr(g, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "Request body is required"}), 400

        validated = PlanCreateSchema.model_validate(payload)
        plan_request = validated.model_dump()

        user_timezone = resolve_timezone(plan_request) or "UTC"
        plan_request["user_timezone"] = user_timezone
        activity_weeks = int(payload.get("activity_weeks", 12) or 12)

        with get_session() as session:
            result = run_v2_plan_generation(
                session=session,
                user_id=str(user_id),
                plan_request=plan_request,
                activity_weeks=activity_weeks,
                mode="prefill",
            )
            draft_payload = build_standard_draft_payload(
                validation_result=result, timezone=user_timezone
            )
            draft_payload["plan_request"] = plan_request
            return jsonify({"status": "success", "draft": draft_payload}), 200

    except ValueError as exc:
        logger.error("Validation error in v2 draft route: %s", exc)
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Unexpected error generating v2 draft plan: %s", exc)
        return jsonify({"error": "Failed to generate draft plan"}), 500
