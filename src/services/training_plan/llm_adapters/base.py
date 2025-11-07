from typing import Any, Dict, List, Protocol


class LLMClient(Protocol):
    def completion(
        self, messages: List[Dict[str, str]], config: Dict[str, Any]
    ) -> str:  # pragma: no cover
        ...
