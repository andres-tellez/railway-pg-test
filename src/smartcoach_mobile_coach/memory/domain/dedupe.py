"""
Purpose:
- Define dedupe policy interface and similarity helper contracts.

Responsibilities:
- Provide typed contracts for memory dedupe decisions.

Non-goals:
- No DB interaction.
"""

from __future__ import annotations

from typing import Protocol

from src.smartcoach_mobile_coach.memory.domain.types import DurableItem


class DedupePolicy(Protocol):
    def is_duplicate(
        self, *, candidate_text: str, existing_item: DurableItem
    ) -> bool: ...


class SimilarityScorer(Protocol):
    def similarity(self, *, a: str, b: str) -> float: ...
