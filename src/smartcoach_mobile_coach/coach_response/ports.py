"""Protocol contracts for coach_response adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class FactRetriever(Protocol):
    def build_context(self, **kwargs: Any) -> Any: ...


class PromptComposer(Protocol):
    def build_messages(
        self,
        *,
        base_system_content: str,
        context: Any,
        coach_snapshot: Optional[Dict[str, Any]],
        conversation_history: List[Dict[str, str]],
        user_message: str,
        history_window: int,
    ) -> List[Dict[str, str]]: ...


class LLMResponder(Protocol):
    def chat_completion(self, **kwargs: Any) -> Any: ...
