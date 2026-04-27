"""
Shared helpers for invoking the refactored v2 plan generation pipeline.
"""

from __future__ import annotations

import logging
import uuid as uuid_mod
from typing import Any, Dict, Literal, Optional, Tuple

from sqlalchemy.orm import Session

from src.services.training_plan.v2.race_distance_factory_v2 import (
    get_race_distance_services,
    normalize_race_distance,
)
from src.services.training_plan.v2.plan_generation_orchestrator_v2 import (
    PlanGenerationOrchestratorV2,
)
from src.db.dao.user_profile_dao import get_user_profile

logger = logging.getLogger(__name__)


def run_v2_plan_generation(
    *,
    session: Session,
    user_id: str,
    plan_request: Dict[str, Any],
    activity_weeks: int = 12,
    mode: str = "prefill",  # Default to detailing every week
    memory_mode: Literal["on", "off"] = "on",
) -> Dict[str, Any]:
    """
    Execute the v2 LR-first deterministic pipeline and return the validation payload.
    """

    training_days = plan_request.get("training_days")

    plan_request.pop("coach_memory_hints", None)
    plan_request.pop("coach_memory_memories", None)
    if memory_mode == "on":
        # Phase G — surface memory inputs, but resolve long_run_day in one shared place.
        try:
            uid_u = uuid_mod.UUID(str(user_id))
            from src.services.coach.user_plan_memory_service import (
                coach_memory_entries_for_plan_generation,
                coach_memory_hints_for_plan_generation,
            )

            hints = coach_memory_hints_for_plan_generation(session, uid_u)
            memories = coach_memory_entries_for_plan_generation(session, uid_u)
            if hints:
                plan_request["coach_memory_hints"] = hints
            if memories:
                plan_request["coach_memory_memories"] = memories
        except Exception:
            logger.debug(
                "[run_v2_plan_generation] coach memory inputs skipped", exc_info=True
            )

    race_label = normalize_race_distance(plan_request.get("race_distance", "Marathon"))
    plan_request["race_distance"] = race_label

    services = get_race_distance_services(race_label)
    config = services["race_config"]
    race_type = services["race_type"]  # Extract race_type for template lookup

    orchestrator = PlanGenerationOrchestratorV2(
        config=config,
        race_type=race_type,  # Pass race_type so Step 6 uses correct templates
    )

    # Fetch user profile to get unit_system preference
    user_profile = get_user_profile(session, str(user_id))
    unit_system = (
        (user_profile.get("unit_system") or "imperial") if user_profile else "imperial"
    )

    runner_ctx = {
        "session": session,
        "user_id": str(user_id),
        "plan_request": plan_request,
        "training_days": training_days,
        "activity_weeks": activity_weeks,
        "unit_system": unit_system,  # Pass unit system for unit-aware rounding
    }
    validation = orchestrator.generate_longrun_first(runner_ctx, mode=mode)
    snapshot = runner_ctx.pop("_context_snapshot_for_persist", None)
    print("SNAPSHOT AFTER POP:", snapshot is not None)
    return validation, snapshot


def build_standard_draft_payload(
    *,
    validation_result: Dict[str, Any],
    timezone: Optional[str] = None,
    context_snapshot: Optional[Dict[str, Any]] = None,
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

    validation_block: Dict[str, Any] = {
        "valid": bool(validation_result.get("valid")),
        "violations": validation_result.get("violations", []),
        "validated_plan": validation_result.get("validated_plan"),
        "decision_trace": validation_result.get("decision_trace", []),
        "spine_quality": validation_result.get(
            "spine_quality"
        ),  # Include spine quality validation (cutback spacing, progression, etc.)
    }
    if context_snapshot is not None:
        validation_block["context_snapshot"] = context_snapshot

    draft_payload: Dict[str, Any] = {
        "generated_plan": generated_plan or {},
        "validation": validation_block,
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
