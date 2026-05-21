"""
Purpose:
- Define read-side composed MemoryView contracts.

Responsibilities:
- Represent memory payload after composition and budget trimming.

Non-goals:
- No rendering or persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.smartcoach_mobile_coach.memory.domain.types import (
    DurableItem,
    InteractionRecord,
    OpenThread,
    SessionSummaryItem,
    StateObservation,
)
from src.smartcoach_mobile_coach.memory.domain.vocab import MemoryKind


@dataclass(frozen=True)
class ViewDiagnostics:
    schema_version: int
    built_at: datetime
    kinds_included: tuple[MemoryKind, ...]
    kinds_omitted_due_to_flag: tuple[MemoryKind, ...]
    fields_omitted_due_to_budget: tuple[str, ...]
    chars_total: int
    chars_budget: int


@dataclass(frozen=True)
class MemoryView:
    durable: tuple[DurableItem, ...]
    state: tuple[StateObservation, ...]
    threads_due: tuple[OpenThread, ...]
    interaction: tuple[InteractionRecord, ...]
    summary: SessionSummaryItem | None
    diagnostics: ViewDiagnostics
