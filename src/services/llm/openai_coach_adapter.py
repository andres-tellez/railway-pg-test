"""
Adapter implementing :class:`~src.services.training_plan.v2.plan_coach.PlanCoachLLMClient`
via :class:`~src.services.security.external_apis.openai_service.OpenAIService`.
"""

from __future__ import annotations

from src.services.security.external_apis.openai_service import OpenAIService


class OpenAICoachAdapter:
    def __init__(self, openai_service: OpenAIService, user_id: str | None = None):
        self.client = openai_service
        self.user_id = user_id

    def chat(self, *, system: str, user: str, temperature: float) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        response = self.client.chat_completion(
            messages=messages,
            user_id=self.user_id,
            temperature=temperature,
        )

        return response.content
