"""
Shared helpers for invoking the refactored v2 plan generation pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.services.training_plan.v2.race_distance_factory_v2 import (
    get_race_distance_services,
    normalize_race_distance,
)
from src.services.training_plan.v2.plan_generation_orchestrator_v2 import (
    PlanGenerationOrchestratorV2,
)
from src.utils.date_helpers import DEFAULT_TRAINING_DAYS


def run_v2_plan_generation(
    *,
    session: Session,
    user_id: str,
    plan_request: Dict[str, Any],
    activity_weeks: int = 12,
    mode: str = "prefill",  # Default to detailing every week
) -> Dict[str, Any]:
    """
    Execute the v2 LR-first deterministic pipeline and return the validation payload.
    """

    training_days = plan_request.get("training_days") or DEFAULT_TRAINING_DAYS
    if not plan_request.get("training_days"):
        plan_request["training_days"] = training_days

    race_label = normalize_race_distance(plan_request.get("race_distance", "Marathon"))
    plan_request["race_distance"] = race_label

    services = get_race_distance_services(race_label)
    config = services["race_config"]

    orchestrator = PlanGenerationOrchestratorV2(config=config)
    runner_ctx = {
        "session": session,
        "user_id": str(user_id),
        "plan_request": plan_request,
        "training_days": training_days,
        "activity_weeks": activity_weeks,
    }
    return orchestrator.generate_longrun_first(runner_ctx, mode=mode)


def build_standard_draft_payload(
    *,
    validation_result: Dict[str, Any],
    timezone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert the orchestrator's validation payload into the frontend-friendly draft format.
    """

    generated_plan = validation_result.get("draft") or validation_result.get(
        "validated_plan"
    )
    if generated_plan and timezone:
        # Avoid mutating original object
        generated_plan = {**generated_plan, "timezone": timezone}

    draft_payload: Dict[str, Any] = {
        "generated_plan": generated_plan or {},
        "validation": {
            "valid": bool(validation_result.get("valid")),
            "violations": validation_result.get("violations", []),
            "validated_plan": validation_result.get("validated_plan"),
            "spine_quality": validation_result.get(
                "spine_quality"
            ),  # Include spine quality validation (cutback spacing, progression, etc.)
        },
        "recovery_metadata": validation_result.get("recovery_metadata"),
        "pass1_rationale": validation_result.get("pass1_rationale"),
        "race_date_validation": validation_result.get("race_date_validation"),
    }

    # Backwards-compatibility for clients that used the beta /plan-v2/draft payload
    draft_payload["draft"] = draft_payload["generated_plan"]
    draft_payload["valid"] = draft_payload["validation"]["valid"]
    draft_payload["violations"] = draft_payload["validation"]["violations"]
    draft_payload["raw_result"] = validation_result

    return draft_payload
