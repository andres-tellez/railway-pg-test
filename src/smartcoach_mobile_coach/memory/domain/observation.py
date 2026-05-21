"""
Purpose:
- Define write-side observation input shape for MemoryService.record().

Responsibilities:
- Capture the minimum typed input required to classify and route memory writes.

Non-goals:
- No classification logic.

Guardrails:
- Allowed imports/calls: dataclasses + typing + uuid + domain types only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import UUID

from src.smartcoach_mobile_coach.memory.domain.types import Provenance
from src.smartcoach_mobile_coach.memory.domain.vocab import MemoryKind


@dataclass(frozen=True)
class Observation:
    user_id: UUID
    text: str
    provenance: Provenance
    kind: MemoryKind | None = None
    hints: Mapping[str, Any] = field(default_factory=dict)
