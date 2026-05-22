"""Compatibility wrappers for plan-generation imports."""

from src.db.dao.user_profile_dao import get_user_profile
from src.smartcoach_mobile_coach.plan_generation import (
    build_standard_draft_payload,
    run_v2_plan_generation,
)

__all__ = [
    "build_standard_draft_payload",
    "get_user_profile",
    "run_v2_plan_generation",
]
