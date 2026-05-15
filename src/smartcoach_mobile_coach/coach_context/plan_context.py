"""
Purpose:
- Build the compact always-on plan slice for CoachSnapshot.

Responsibilities:
- Resolve active-plan state via the canonical plan service facade.
- Map race + phase essentials from user_context payload into a compact shape.

Non-goals:
- No SQL queries in this module.
- No plan verdict logic, no weekly-plan expansion.

Guardrails:
- Allowed imports/calls: `src.services.plan.active_plan.has_active_plan` and
  user_context payload data passed in by caller.
- Must not import from `src.smartcoach_mobile_coach.orchestrator`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.services.plan.active_plan import has_active_plan
from src.smartcoach_mobile_coach.coach_context.schemas import PlanSlice


def _compact_race(race_goal: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(race_goal, dict):
        return None
    race = {
        "name": race_goal.get("race_name"),
        "distance": race_goal.get("race_distance"),
        "date": race_goal.get("race_date"),
        "weeks_until": race_goal.get("weeks_until_race"),
        "goal_time": race_goal.get("goal_time"),
    }
    if any(v is not None and v != "" for v in race.values()):
        return race
    return None


def _compact_phase(plan_block: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(plan_block, dict):
        return None
    raw_priority = plan_block.get("phase_kpi_priority")
    kpis = []
    if isinstance(raw_priority, list):
        for item in raw_priority:
            if isinstance(item, dict):
                if isinstance(item.get("label"), str) and item["label"].strip():
                    kpis.append(item["label"].strip())
                elif isinstance(item.get("kpi_id"), str) and item["kpi_id"].strip():
                    kpis.append(item["kpi_id"].strip())
    phase = {
        "label": plan_block.get("current_phase"),
        "week_in_phase": plan_block.get("current_week_number"),
        "kpi_priority": kpis[:3],
    }
    if any(v is not None and v != [] and v != "" for v in phase.values()):
        return phase
    return None


def build_plan_slice(
    *,
    session: Session,
    internal_user_id: str,
    user_context_payload: Dict[str, Any],
) -> PlanSlice:
    """Build the compact plan slice from canonical sources."""
    active = has_active_plan(session, str(internal_user_id))
    race = _compact_race(user_context_payload.get("race_goal"))
    phase = _compact_phase(user_context_payload.get("plan"))
    if not active:
        race = None
        phase = None
    return PlanSlice(
        has_active_plan=active,
        race=race,
        phase=phase,
    )
