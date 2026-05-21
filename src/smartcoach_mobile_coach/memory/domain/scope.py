"""
Purpose:
- Define read-side query scope for MemoryService.get_view().

Responsibilities:
- Provide a deterministic set of filtering hints for memory composition.

Non-goals:
- No runtime query logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from src.smartcoach_mobile_coach.memory.domain.vocab import MemoryKind


@dataclass(frozen=True)
class Scope:
    user_id: UUID
    now: datetime
    conversation_id: UUID | None
    local_date: date | None
    opening_turn: bool
    activity_id: int | None
    intent_hints: tuple[str, ...] = ()
    include_kinds: frozenset[MemoryKind] | None = None
    budget_chars: int = 1200
    tags: tuple[str, ...] = field(default_factory=tuple)
