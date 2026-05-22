"""Coach-facing plan-generation package surface."""

from src.smartcoach_mobile_coach.plan_generation.coordinator import (
    generate_training_plan_tool,
)
from src.smartcoach_mobile_coach.plan_generation.draft_payload import (
    build_standard_draft_payload,
)
from src.smartcoach_mobile_coach.plan_generation.facade import (
    generate_plan_for_coach,
    run_v2_plan_generation,
)
from src.smartcoach_mobile_coach.plan_generation.request_builder import (
    build_plan_request_from_state,
)

__all__ = [
    "build_plan_request_from_state",
    "build_standard_draft_payload",
    "generate_plan_for_coach",
    "generate_training_plan_tool",
    "run_v2_plan_generation",
]
