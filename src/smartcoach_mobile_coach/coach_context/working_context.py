"""
Purpose:
- Build non-persistent working-context slice from conversation history.

Responsibilities:
- Reuse DerivedThreadCoachContext parsing for follow-up references.
- Emit only compact flags relevant to turn continuity.

Non-goals:
- No persistence or DB writes.
- No intent classification replacement.

Guardrails:
- Allowed imports/calls: `derive_thread_coach_context` only.
- Must not import orchestrator.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.smartcoach_mobile_coach.coach_context.schemas import WorkingContextSlice
from src.smartcoach_mobile_coach.thread_derived_context import (
    derive_thread_coach_context,
)


def build_working_slice(
    *,
    conversation_history: List[Dict[str, str]],
) -> Optional[WorkingContextSlice]:
    """Build compact working-context slice from prior turns."""
    derived = derive_thread_coach_context(conversation_history or [])
    if (
        derived.last_structured_run_activity_id is None
        and not derived.prior_run_summary_in_thread
        and not derived.plan_creation_clarification_pending
    ):
        return None
    return WorkingContextSlice(
        last_structured_run_activity_id=derived.last_structured_run_activity_id,
        prior_run_summary_in_thread=bool(derived.prior_run_summary_in_thread),
        plan_creation_clarification_pending=bool(
            derived.plan_creation_clarification_pending
        ),
    )
