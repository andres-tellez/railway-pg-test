"""
Purpose:
- Define prompt rendering interface for MemoryView.

Responsibilities:
- Provide typed contracts for deterministic prompt-safe rendering.

Non-goals:
- No prompt orchestration or side effects.
"""

from __future__ import annotations

from typing import Protocol

from src.smartcoach_mobile_coach.memory.domain.view import MemoryView


class MemoryPromptRenderer(Protocol):
    def render(self, *, view: MemoryView) -> str: ...
