"""
Purpose:
- Define redaction policy contracts for memory content safety.

Responsibilities:
- Provide typed interface for sanitizing memory text before prompt rendering.

Non-goals:
- No persistence writes.
"""

from __future__ import annotations

from typing import Protocol

from src.smartcoach_mobile_coach.memory.domain.view import MemoryView


class RedactionPolicy(Protocol):
    def apply(self, *, view: MemoryView) -> MemoryView: ...
