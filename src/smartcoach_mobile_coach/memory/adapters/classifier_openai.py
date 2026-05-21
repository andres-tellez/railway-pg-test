"""
Purpose:
- OpenAI-backed client adapter for memory observation classification.

Responsibilities:
- Call the unified OpenAI service with JSON schema instructions.
- Return normalized payload consumed by LLMObservationClassifier.

Non-goals:
- No fallback policy logic.
- No persistence writes.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from src.services.security.external_apis.openai_service import get_openai_service

_CLASSIFIER_PROMPT = (
    "Classify a user statement into memory shape.\n"
    "Return JSON only with keys:\n"
    '- memory_kind: "durable"|"state"|"open_thread"|"interaction"|"summary"\n'
    '- durable_type: "goal"|"constraint"|"preference"|"training_days"|"long_run_day"|"other" (required only for durable)\n'
    "- confidence: float in [0,1]\n"
    "Rules:\n"
    "- Use durable for long-lived preferences, constraints, and goals.\n"
    "- Use state for short-lived body/feeling updates.\n"
    "- Use open_thread when user asks to revisit later.\n"
    "- Use interaction or summary only when explicit request is about thread handling.\n"
    "- If unsure, choose durable with durable_type=other and low confidence.\n"
)


class OpenAIClassifierClient:
    """Classifier client adapter backed by OpenAIService."""

    def __init__(self, *, model: str = "gpt-4o-mini") -> None:
        self._model = model

    def classify(
        self, *, text: str, user_id: str, timeout_s: float
    ) -> Mapping[str, Any]:
        svc = get_openai_service()
        resp = svc.chat_completion(
            messages=[
                {"role": "system", "content": _CLASSIFIER_PROMPT},
                {"role": "user", "content": text[:2000]},
            ],
            user_id=user_id,
            model=self._model,
            temperature=0.0,
            max_tokens=120,
            timeout=timeout_s,
            require_json=True,
        )
        parsed: Dict[str, Any]
        try:
            parsed = json.loads(resp.content or "{}")
        except json.JSONDecodeError:
            parsed = {}
        parsed["cost"] = resp.cost
        parsed["model"] = resp.model
        parsed["usage_total_tokens"] = int((resp.usage or {}).get("total_tokens") or 0)
        return parsed
