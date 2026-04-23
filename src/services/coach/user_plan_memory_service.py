"""Phase F — read/write user plan memories (Layer C)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from src.db.models.user_plan_memories import (
    MEMORY_SOURCE_COACH_TOOL,
    MEMORY_SOURCE_SESSION_SUMMARY,
    UserPlanMemory,
)

_MAX_MEMORY_CHARS = 280
_MAX_CONTEXT_MEMORIES = 8
_MAX_HINT_CHARS = 600
_MAX_MEMORIES_PER_USER = 20
_DEDUPE_SIMILARITY_THRESHOLD = 0.85

# Selection order for get_user_context (lower = earlier in list).
_VALID_MEMORY_TYPES = frozenset(
    {
        "long_run_day",
        "training_days",
        "goal",
        "constraint",
        "preference",
        "other",
    }
)

_MEMORY_TYPE_PRIORITY: Dict[Optional[str], int] = {
    "constraint": 0,
    "training_days": 1,
    "long_run_day": 2,
    "goal": 3,
    "preference": 4,
    "other": 5,
    None: 6,
}

_WEEKDAY_WORDS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
)


def _normalize_memory_text(raw: str) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    t = raw.strip()
    if not t:
        return None
    if len(t) > _MAX_MEMORY_CHARS:
        t = t[:_MAX_MEMORY_CHARS].rstrip()
    return t


def _normalized_for_similarity(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]+", " ", s, flags=re.UNICODE)
    return " ".join(s.split())


def memory_text_similarity(a: str, b: str) -> float:
    """Lightweight fuzzy match for dedupe (no embeddings)."""
    na, nb = _normalized_for_similarity(a), _normalized_for_similarity(b)
    if not na or not nb:
        return 0.0
    return float(SequenceMatcher(None, na, nb).ratio())


def infer_memory_type(text: str) -> str:
    """Keyword-only type guess (no LLM). First high-signal rule wins."""
    l = text.lower()

    if re.search(
        r"\b(injur|doctor|physio|must avoid|cannot run|can't run|never run|"
        r"no doubles|no back-to-back|limited to|only able to|do not run|"
        r"avoid running|not allowed to run)\b",
        l,
    ):
        return "constraint"
    if "can't" in l or "cannot " in l or "must not" in l:
        return "constraint"

    if re.search(
        r"\b(\d+)\s*(day|days|time|times)\s*(per week|each week|a week)\b", l
    ) or re.search(r"\bonly run\s+\d\b", l):
        return "training_days"
    if "days per week" in l or "train only" in l or "run only" in l:
        return "training_days"
    if "which days" in l and "run" in l:
        return "training_days"

    if ("long run" in l or "long-run" in l or "longrun" in l) and any(
        w in l for w in _WEEKDAY_WORDS
    ):
        return "long_run_day"
    if re.search(r"\blong run\b.*\b(on|after|before)\b", l):
        return "long_run_day"

    if re.search(
        r"\b(goal|qualify|qualifying|sub-\d|sub \d|finish a marathon|"
        r"pr\b|pb\b|personal best|race time)\b",
        l,
    ):
        return "goal"

    if re.search(r"\b(prefer|rather|would like|i like to|i'd like to)\b", l):
        return "preference"

    return "other"


def _find_semantic_duplicate(
    session: Session,
    user_id: uuid.UUID,
    text: str,
) -> Optional[UserPlanMemory]:
    rows = (
        session.query(UserPlanMemory)
        .filter(UserPlanMemory.user_id == user_id)
        .order_by(UserPlanMemory.created_at.desc())
        .limit(_MAX_MEMORIES_PER_USER)
        .all()
    )
    for row in rows:
        existing = (row.memory_text or "").strip()
        if not existing:
            continue
        if memory_text_similarity(text, existing) >= _DEDUPE_SIMILARITY_THRESHOLD:
            return row
    return None


def _evict_oldest_if_at_cap(session: Session, user_id: uuid.UUID) -> None:
    """Keep at most ``_MAX_MEMORIES_PER_USER - 1`` rows so one insert stays at cap."""
    while True:
        cnt = (
            session.query(UserPlanMemory)
            .filter(UserPlanMemory.user_id == user_id)
            .count()
        )
        if cnt < _MAX_MEMORIES_PER_USER:
            break
        oldest = (
            session.query(UserPlanMemory)
            .filter(UserPlanMemory.user_id == user_id)
            .order_by(UserPlanMemory.created_at.asc())
            .first()
        )
        if oldest is None:
            break
        session.delete(oldest)
        session.flush()


def append_plan_memory(
    session: Session,
    user_id: uuid.UUID,
    memory_text: str,
    *,
    source: str,
    memory_type: Optional[str] = None,
) -> Tuple[Optional[UserPlanMemory], bool]:
    """Insert one memory row when not a near-duplicate.

    Returns ``(row, deduplicated)`` where ``deduplicated`` is True when an
    existing row matched at similarity >= threshold (no insert).
    """
    text = _normalize_memory_text(memory_text)
    if text is None:
        return None, False
    if source not in (MEMORY_SOURCE_COACH_TOOL, MEMORY_SOURCE_SESSION_SUMMARY):
        return None, False

    mtype = memory_type if memory_type else infer_memory_type(text)
    if mtype not in _VALID_MEMORY_TYPES:
        mtype = "other"

    dup = _find_semantic_duplicate(session, user_id, text)
    if dup is not None:
        return dup, True

    _evict_oldest_if_at_cap(session, user_id)

    row = UserPlanMemory(
        user_id=user_id,
        memory_text=text,
        source=source,
        memory_type=mtype,
    )
    session.add(row)
    session.flush()
    return row, False


def _memory_type_priority(mt: Optional[str]) -> int:
    return _MEMORY_TYPE_PRIORITY.get(mt, _MEMORY_TYPE_PRIORITY[None])


def _memory_sort_key(row: UserPlanMemory) -> Tuple[int, float]:
    pri = _memory_type_priority(getattr(row, "memory_type", None))
    created = row.created_at
    if isinstance(created, datetime):
        ts = created.timestamp()
    else:
        ts = 0.0
    return (pri, -ts)


def _load_memories_for_selection(
    session: Session, user_id: uuid.UUID
) -> List[UserPlanMemory]:
    """All rows for user (bounded) for prioritization."""
    cap = max(_MAX_MEMORIES_PER_USER, _MAX_CONTEXT_MEMORIES) + 5
    rows = (
        session.query(UserPlanMemory)
        .filter(UserPlanMemory.user_id == user_id)
        .order_by(UserPlanMemory.created_at.desc())
        .limit(cap)
        .all()
    )
    rows.sort(key=_memory_sort_key)
    return rows


def memories_for_user_context(
    session: Session, user_id: uuid.UUID
) -> List[Dict[str, Any]]:
    """Wire shape for ``get_user_context`` — max 8, type-priority then recency."""
    rows = _load_memories_for_selection(session, user_id)[:_MAX_CONTEXT_MEMORIES]
    out: List[Dict[str, Any]] = []
    for r in rows:
        created = r.created_at
        if isinstance(created, datetime):
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            created_iso = created.isoformat()
        else:
            created_iso = None
        mt = getattr(r, "memory_type", None)
        item: Dict[str, Any] = {
            "id": str(r.id),
            "text": r.memory_text,
            "source": r.source,
            "created_at": created_iso,
        }
        if mt:
            item["memory_type"] = mt
        out.append(item)
    return out


def coach_memory_hints_for_plan_generation(
    session: Session,
    user_id: uuid.UUID,
) -> List[str]:
    """Short strings — same priority order as context, then take five."""
    rows = _load_memories_for_selection(session, user_id)[:5]
    hints: List[str] = []
    total = 0
    for r in rows:
        fragment = (r.memory_text or "").strip()
        if not fragment:
            continue
        if len(fragment) > 160:
            fragment = fragment[:157].rstrip() + "…"
        if total + len(fragment) > _MAX_HINT_CHARS:
            break
        hints.append(fragment)
        total += len(fragment)
    return hints


def coach_memory_entries_for_plan_generation(
    session: Session,
    user_id: uuid.UUID,
) -> List[Dict[str, Any]]:
    """Structured memory rows aligned with plan-generation hint priority."""
    rows = _load_memories_for_selection(session, user_id)[:5]
    out: List[Dict[str, Any]] = []
    for r in rows:
        fragment = (r.memory_text or "").strip()
        if not fragment:
            continue
        if len(fragment) > 160:
            fragment = fragment[:157].rstrip() + "…"
        item: Dict[str, Any] = {
            "id": str(r.id),
            "text": fragment,
            "source": r.source,
        }
        mt = getattr(r, "memory_type", None)
        if mt:
            item["memory_type"] = mt
        out.append(item)
    return out


_DAY_ALIASES = (
    ("saturday", "Sat"),
    ("sunday", "Sun"),
    ("monday", "Mon"),
    ("tuesday", "Tue"),
    ("wednesday", "Wed"),
    ("thursday", "Thu"),
    ("friday", "Fri"),
)


def infer_long_run_day_from_memory_hints(
    hints: Sequence[str],
    training_days: Sequence[str],
) -> Optional[str]:
    """If memories clearly prefer a weekday for long runs, map into ``training_days``."""
    if not hints or not training_days:
        return None
    blob = " ".join(hints).lower()
    if "long run" not in blob and "long-run" not in blob and "longrun" not in blob:
        return None
    for word, abbrev in _DAY_ALIASES:
        if word in blob or re.search(rf"\b{abbrev.lower()}\b", blob):
            if abbrev in training_days:
                return abbrev
    return None
