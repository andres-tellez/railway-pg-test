"""Coach memory hint injection for plan generation."""

# pylint: disable=import-outside-toplevel,broad-exception-caught

from __future__ import annotations

import logging
import uuid as uuid_mod
from typing import Any, Dict, Literal

from sqlalchemy.orm import Session

logger = logging.getLogger("smartcoach_mobile_coach")


def attach_coach_memory_inputs(
    *,
    session: Session,
    user_id: str,
    plan_request: Dict[str, Any],
    memory_mode: Literal["on", "off"] = "on",
) -> None:
    """Populate plan_request with coach memory hints/memories in-place."""
    plan_request.pop("coach_memory_hints", None)
    plan_request.pop("coach_memory_memories", None)
    if memory_mode != "on":
        return

    try:
        uid_u = uuid_mod.UUID(str(user_id))
        from src.smartcoach_mobile_coach.memory.plan_memory_store import (
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
            "[generate_plan_for_coach] coach memory inputs skipped", exc_info=True
        )
