"""
Plan Routes V2 - Refactored deterministic draft plan endpoint
"""

from flask import Blueprint, jsonify, request, g
import logging

from src.db.db_session import get_session
from src.schemas.plan_schema import PlanCreateSchema
from src.services.training_plan.v2.race_distance_factory_v2 import (
    get_race_distance_services,
    normalize_race_distance,
)
from src.services.training_plan.v2.plan_generation_orchestrator_v2 import (
    PlanGenerationOrchestratorV2,
)
from src.utils.auth0_jwt import requires_auth

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

        # Determine race distance config
        race_distance_label = normalize_race_distance(
            plan_request.get("race_distance", "Marathon")
        )
        services = get_race_distance_services(race_distance_label)
        config = services["race_config"]

        training_days = plan_request.get("training_days")
        if not training_days:
            from src.utils.date_helpers import DEFAULT_TRAINING_DAYS

            training_days = DEFAULT_TRAINING_DAYS

        with get_session() as session:
            orchestrator = PlanGenerationOrchestratorV2(config=config)
            runner_ctx = {
                "session": session,
                "user_id": str(user_id),
                "plan_request": plan_request,
                "training_days": training_days,
                "activity_weeks": payload.get("activity_weeks", 12),
            }
            result = orchestrator.generate_longrun_first(runner_ctx, mode="prefill")
            return jsonify({"status": "success", "draft": result}), 200

    except ValueError as exc:
        logger.error("Validation error in v2 draft route: %s", exc)
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Unexpected error generating v2 draft plan: %s", exc)
        return jsonify({"error": "Failed to generate draft plan"}), 500
