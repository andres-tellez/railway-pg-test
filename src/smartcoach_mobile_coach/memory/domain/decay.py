"""
Purpose:
- Define decay policy interface for time-sensitive memory items.

Responsibilities:
- Provide typed function contracts for determining whether memory is active.

Non-goals:
- No persistence cleanup or scheduling logic.
"""

from __future__ import annotations

from typing import Protocol

from src.smartcoach_mobile_coach.memory.domain.types import StateObservation
from src.smartcoach_mobile_coach.memory.domain.scope import Scope


class DecayPolicy(Protocol):
    def is_active(self, *, item: StateObservation, scope: Scope) -> bool: ...
