"""Facade for invoking deterministic plan generation from coach flows."""

# pylint: disable=too-many-arguments

from __future__ import annotations

from typing import Any, Dict, Literal, Tuple

from sqlalchemy.orm import Session

from src.db.dao.user_profile_dao import get_user_profile
from src.services.training_plan.v2.plan_generation_orchestrator_v2 import (
    PlanGenerationOrchestratorV2,
)
from src.services.training_plan.v2.race_distance_factory_v2 import (
    get_race_distance_services,
    normalize_race_distance,
)
from src.smartcoach_mobile_coach.plan_generation.coach_memory_glue import (
    attach_coach_memory_inputs,
)


def generate_plan_for_coach(
    *,
    session: Session,
    user_id: str,
    plan_request: Dict[str, Any],
    activity_weeks: int = 12,
    mode: str = "prefill",
    memory_mode: Literal["on", "off"] = "on",
) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
    """
    Execute deterministic v2 pipeline and return validation plus context snapshot.
    """
    training_days = plan_request.get("training_days")

    attach_coach_memory_inputs(
        session=session,
        user_id=str(user_id),
        plan_request=plan_request,
        memory_mode=memory_mode,
    )

    race_label = normalize_race_distance(plan_request.get("race_distance", "Marathon"))
    plan_request["race_distance"] = race_label

    services = get_race_distance_services(race_label)
    orchestrator = PlanGenerationOrchestratorV2(
        config=services["race_config"],
        race_type=services["race_type"],
    )

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
        "unit_system": unit_system,
    }
    validation = orchestrator.generate_longrun_first(runner_ctx, mode=mode)
    snapshot = runner_ctx.pop("_context_snapshot_for_persist", None)
    return validation, snapshot


# Temporary compatibility alias while call sites migrate.
run_v2_plan_generation = generate_plan_for_coach
