"""Plan-intake to planner-request adapter entrypoint."""

from __future__ import annotations

from src.smartcoach_mobile_coach.plan_intake_flow import build_plan_request_from_state

__all__ = ["build_plan_request_from_state"]
