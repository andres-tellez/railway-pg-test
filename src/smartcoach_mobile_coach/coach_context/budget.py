"""
Purpose:
- Enforce a compact CoachSnapshot size budget.

Responsibilities:
- Estimate rendered snapshot size.
- Apply deterministic drop policy and record omitted field paths.

Non-goals:
- No tokenization library integration.
- No data fetching.

Guardrails:
- Allowed imports/calls: stdlib + schema dataclasses only.
- Must not import orchestrator or DB services.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import List, Tuple

from src.smartcoach_mobile_coach.coach_context.schemas import (
    CoachSnapshot,
    MemorySlice,
    WorkingContextSlice,
    AthleteSlice,
)

DEFAULT_MAX_CHARS = 2400


def estimate_snapshot_chars(snapshot: CoachSnapshot) -> int:
    """Approximate serialized snapshot size in chars."""
    return len(json.dumps(snapshot.to_dict(), separators=(",", ":"), default=str))


def apply_budget(
    snapshot: CoachSnapshot, *, max_chars: int = DEFAULT_MAX_CHARS
) -> Tuple[CoachSnapshot, List[str], int]:
    """
    Apply drop policy until serialized snapshot fits the char budget.

    Drop order:
    1) memory.session_summary_excerpt
    2) memory.plan_memories (tail-first, then empty)
    3) trends (entire slice)
    4) working non-critical flags
    5) athlete.zones_compact
    """
    updated = replace(snapshot, omitted_fields=list(snapshot.omitted_fields or []))
    omitted = list(updated.omitted_fields)

    def _size() -> int:
        return estimate_snapshot_chars(updated)

    def _mark(path: str) -> None:
        if path not in omitted:
            omitted.append(path)

    if _size() <= max_chars:
        updated.omitted_fields = omitted
        return updated, omitted, _size()

    mem = updated.memory
    if mem is not None and mem.session_summary_excerpt:
        updated.memory = replace(mem, session_summary_excerpt=None)
        _mark("memory.session_summary_excerpt")
    while _size() > max_chars and updated.memory and updated.memory.plan_memories:
        cur = list(updated.memory.plan_memories)
        cur.pop()
        updated.memory = replace(updated.memory, plan_memories=cur)
        _mark("memory.plan_memories")
    if (
        updated.memory is not None
        and not updated.memory.plan_memories
        and not updated.memory.session_summary_excerpt
    ):
        updated.memory = None

    if _size() > max_chars and updated.trends is not None:
        updated.trends = None
        _mark("trends")

    if _size() > max_chars and updated.working is not None:
        wk: WorkingContextSlice = updated.working
        if wk.plan_creation_clarification_pending:
            wk = replace(wk, plan_creation_clarification_pending=False)
            _mark("working.plan_creation_clarification_pending")
        if _size() > max_chars and wk.prior_run_summary_in_thread:
            wk = replace(wk, prior_run_summary_in_thread=False)
            _mark("working.prior_run_summary_in_thread")
        if (
            not wk.plan_creation_clarification_pending
            and not wk.prior_run_summary_in_thread
            and wk.last_structured_run_activity_id is None
        ):
            updated.working = None
        else:
            updated.working = wk

    if _size() > max_chars and updated.athlete is not None:
        ath: AthleteSlice = updated.athlete
        if ath.zones_compact is not None:
            updated.athlete = replace(ath, zones_compact=None)
            _mark("athlete.zones_compact")

    if _size() > max_chars and updated.memory is not None:
        updated.memory = None
        _mark("memory")

    updated.omitted_fields = omitted
    return updated, omitted, _size()
