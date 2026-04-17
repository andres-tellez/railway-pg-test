"""
Derive short, per-request coach context from stored conversation history only.

No DB columns or persisted flags — parse prior assistant payloads (e.g. run_summary JSON)
so the model gets authoritative hints without relying on plain-text recall alone.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DerivedThreadCoachContext:
    """Flags and ids inferred from chat rows before the current user message."""

    prior_run_summary_in_thread: bool
    """Any prior assistant turn stored as structured run_summary."""

    last_assistant_was_run_summary: bool
    """The chronologically latest assistant message in history is run_summary."""

    last_structured_run_activity_id: Optional[int]
    """activity_id from the newest run_summary in history, if parseable."""

    latest_plan_intake_state: Optional[Dict[str, Any]]
    """Latest deterministic plan intake state from assistant structured payloads."""

    latest_plan_generation_result: Optional[Dict[str, Any]]
    """Latest deterministic plan generation result payload (if present)."""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse_structured_stored(content: str) -> Optional[Dict[str, Any]]:
    stripped = (content or "").strip()
    if not stripped.startswith("{"):
        return None
    try:
        obj: Any = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("type"), str):
        return None
    return obj


def _parse_run_summary_stored(content: str) -> Optional[Dict[str, Any]]:
    obj = _parse_structured_stored(content)
    if not isinstance(obj, dict) or obj.get("type") != "run_summary":
        return None
    return obj


def _activity_id_from_run_summary(obj: Dict[str, Any]) -> Optional[int]:
    data = obj.get("data")
    if not isinstance(data, dict):
        return None
    raw = data.get("activity_id")
    if raw is None and isinstance(data.get("facts"), dict):
        raw = data["facts"].get("activity_id")
    if raw is None:
        comp = data.get("comparison")
        if isinstance(comp, dict):
            tr = comp.get("this_run")
            if isinstance(tr, dict):
                raw = tr.get("activity_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def derive_thread_coach_context(
    conversation_history: List[Dict[str, str]],
) -> DerivedThreadCoachContext:
    """
    Scan prior messages (excludes the message being composed this turn).

    Assistant rows may be compact JSON: {"type":"run_summary","content":...,"data":{...}}.
    """
    any_summary = False
    for m in conversation_history:
        if (m.get("role") or "").strip() != "assistant":
            continue
        if _parse_run_summary_stored(m.get("content") or "") is not None:
            any_summary = True
            break

    last_assistant_was = False
    last_aid: Optional[int] = None
    for m in reversed(conversation_history):
        if (m.get("role") or "").strip() != "assistant":
            continue
        parsed = _parse_run_summary_stored(m.get("content") or "")
        if parsed is not None:
            last_assistant_was = True
            last_aid = _activity_id_from_run_summary(parsed)
        break

    if last_aid is None and any_summary:
        for m in reversed(conversation_history):
            if (m.get("role") or "").strip() != "assistant":
                continue
            parsed = _parse_run_summary_stored(m.get("content") or "")
            if parsed is None:
                continue
            aid = _activity_id_from_run_summary(parsed)
            if aid is not None:
                last_aid = aid
                break

    latest_plan_intake_state: Optional[Dict[str, Any]] = None
    latest_plan_generation_result: Optional[Dict[str, Any]] = None
    for m in reversed(conversation_history):
        if (m.get("role") or "").strip() != "assistant":
            continue
        parsed = _parse_structured_stored(m.get("content") or "")
        if parsed is None:
            continue
        data = parsed.get("data")
        if isinstance(data, dict):
            if latest_plan_intake_state is None and isinstance(
                data.get("plan_intake_state"), dict
            ):
                latest_plan_intake_state = data.get("plan_intake_state")
            if latest_plan_generation_result is None and isinstance(
                data.get("plan_generation"), dict
            ):
                latest_plan_generation_result = data.get("plan_generation")
        if (
            latest_plan_intake_state is not None
            and latest_plan_generation_result is not None
        ):
            break

    return DerivedThreadCoachContext(
        prior_run_summary_in_thread=any_summary,
        last_assistant_was_run_summary=last_assistant_was,
        last_structured_run_activity_id=last_aid,
        latest_plan_intake_state=latest_plan_intake_state,
        latest_plan_generation_result=latest_plan_generation_result,
    )
