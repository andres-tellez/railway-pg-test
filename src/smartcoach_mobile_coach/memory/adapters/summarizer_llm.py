"""LLM adapter for memory summary generation."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence
from uuid import UUID

from src.services.security.external_apis.openai_service import get_openai_service


class SummarizerLLMAdapter:
    """OpenAI-backed summarizer adapter for MemoryService."""

    def __init__(self, *, model: str = "gpt-4o-mini") -> None:
        self._model = model

    def summarize(
        self,
        *,
        user_id: UUID,
        turns: Sequence[Mapping[str, Any]],
        timeout_s: float,
    ) -> Mapping[str, Any]:
        svc = get_openai_service()
        clipped = []
        for t in turns[-8:]:
            role = str(t.get("role") or "")[:20]
            content = str(t.get("content") or "")[:1200]
            clipped.append({"role": role, "content": content})
        resp = svc.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "Summarize the session into compact JSON with keys summary_text, thread_tags.",
                },
                {"role": "user", "content": str(clipped)},
            ],
            user_id=str(user_id),
            model=self._model,
            temperature=0.2,
            max_tokens=300,
            timeout=timeout_s,
            require_json=True,
        )
        return {
            "content": resp.content,
            "usage": resp.usage,
            "cost": resp.cost,
            "model": resp.model,
        }
