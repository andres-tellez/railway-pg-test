"""Build compact memory slice for CoachSnapshot."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.smartcoach_mobile_coach.coach_context.schemas import MemorySlice

_MAX_MEMORY_ITEMS = 2
_MAX_MEMORY_TEXT_CHARS = 120
_MAX_SESSION_EXCERPT_CHARS = 200


def _clean_text(raw: Any, max_chars: int) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    txt = raw.strip()
    if not txt:
        return None
    return txt[:max_chars]


def _compact_plan_memories(raw: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("text"), _MAX_MEMORY_TEXT_CHARS)
        if not text:
            continue
        source_raw = item.get("source")
        source = source_raw.strip() if isinstance(source_raw, str) else "memory"
        out.append({"text": text, "source": source[:32] or "memory"})
        if len(out) >= _MAX_MEMORY_ITEMS:
            break
    return out


def _session_excerpt(raw_summary: Any, opening_turn: bool) -> Optional[str]:
    if not opening_turn or not isinstance(raw_summary, dict):
        return None
    return _clean_text(raw_summary.get("excerpt"), _MAX_SESSION_EXCERPT_CHARS)


def build_memory_slice(
    *,
    user_context_payload: Dict[str, Any],
    opening_turn: bool,
) -> Optional[MemorySlice]:
    plan_memories = _compact_plan_memories(user_context_payload.get("plan_memories"))
    session_excerpt = _session_excerpt(
        user_context_payload.get("session_summary"), opening_turn
    )
    if not plan_memories and not session_excerpt:
        return None
    return MemorySlice(
        plan_memories=plan_memories,
        session_summary_excerpt=session_excerpt,
    )
