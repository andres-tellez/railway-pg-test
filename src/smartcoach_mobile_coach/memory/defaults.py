"""Default lightweight policy implementations for MemoryService wiring."""

from __future__ import annotations

from typing import Sequence

from src.smartcoach_mobile_coach.memory.domain.types import Callback
from src.smartcoach_mobile_coach.memory.domain.view import MemoryView


class NoopCallbackPolicy:
    """V1 default: no proactive callbacks."""

    def choose(self, *, view: MemoryView, budget: int) -> Sequence[Callback]:
        return ()


class BasicPromptRenderer:
    """Minimal deterministic renderer used until richer formatting lands."""

    def render(self, view: MemoryView) -> str:
        sections: list[str] = []
        if view.summary and view.summary.text.strip():
            sections.append(f"## PRIOR SESSION SUMMARY\n{view.summary.text.strip()}")
        if view.durable:
            lines = ["## DURABLE MEMORY"]
            for item in view.durable[:5]:
                lines.append(f"- ({item.durable_type.value}) {item.text}")
            sections.append("\n".join(lines))
        if view.interaction:
            lines = ["## INTERACTION MEMORY"]
            for item in view.interaction[:5]:
                lines.append(f"- ({item.flag.value}) {item.key}")
            sections.append("\n".join(lines))
        return "\n\n".join(sections).strip()
