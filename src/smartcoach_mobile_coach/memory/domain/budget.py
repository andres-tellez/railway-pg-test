"""
Purpose:
- Define memory-view budget policy contracts.

Responsibilities:
- Provide typed interface for trimming memory view content to size budgets.

Non-goals:
- No serialization concerns.
"""

from __future__ import annotations

from typing import Protocol

from src.smartcoach_mobile_coach.memory.domain.scope import Scope
from src.smartcoach_mobile_coach.memory.domain.view import MemoryView


class BudgetPolicy(Protocol):
    def apply(self, *, view: MemoryView, scope: Scope) -> MemoryView: ...
