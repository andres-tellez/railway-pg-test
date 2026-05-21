"""
Purpose:
- Define canonical memory entity dataclasses and service result objects.

Responsibilities:
- Provide immutable typed contracts for service and adapters.

Non-goals:
- No persistence concerns.
- No domain policy logic.

Guardrails:
- Allowed imports/calls: dataclasses, datetime, typing, uuid.
- Must not import adapters or orchestrator modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from src.smartcoach_mobile_coach.memory.domain.vocab import (
    DurableType,
    InteractionFlag,
    MemoryKind,
    Source,
    StateTag,
    ThreadTopic,
)


@dataclass(frozen=True)
class Provenance:
    source: Source
    captured_at: datetime
    conversation_id: UUID | None
    confidence: float = 1.0
    evidence_excerpt: str | None = None


@dataclass(frozen=True)
class DurableItem:
    id: UUID
    user_id: UUID
    text: str
    durable_type: DurableType
    provenance: Provenance


@dataclass(frozen=True)
class StateObservation:
    id: UUID
    user_id: UUID
    text: str
    tag: StateTag
    captured_at: datetime
    valid_until: datetime
    body_area: str | None = None
    intensity: int | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True)
class OpenThread:
    id: UUID
    user_id: UUID
    text: str
    topic: ThreadTopic
    due_at: datetime
    status: Literal["open", "resolved", "snoozed", "stale"]
    created_at: datetime
    provenance: Provenance


@dataclass(frozen=True)
class InteractionRecord:
    id: UUID
    user_id: UUID
    conversation_id: UUID
    flag: InteractionFlag
    key: str
    captured_at: datetime


@dataclass(frozen=True)
class SessionSummaryItem:
    id: UUID
    user_id: UUID
    conversation_id: UUID | None
    text: str
    created_at: datetime
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Callback:
    source_kind: MemoryKind
    source_id: UUID
    suggested_open: str
    cost_chars: int
    confidence: float


@dataclass(frozen=True)
class RecordResult:
    kind: MemoryKind
    action: Literal["created", "deduped", "rejected", "updated"]
    item_id: UUID | None = None
    reason: str | None = None
