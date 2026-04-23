from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from src.services.coach.user_plan_memory_service import (
    infer_long_run_day_from_memory_hints,
)
from src.utils.date_helpers import DAY_NAMES_ABBREV

DecisionSource = Literal["user_input", "memory", "default_fallback"]


@dataclass
class DecisionReason:
    field: str
    value: Any
    source: DecisionSource
    memory_ids: List[str] = field(default_factory=list)
    rationale: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _fallback_long_run_day(training_days: Sequence[str]) -> str:
    if not training_days:
        raise ValueError("training_days must not be empty")
    if DAY_NAMES_ABBREV[5] in training_days:
        return DAY_NAMES_ABBREV[5]
    if DAY_NAMES_ABBREV[6] in training_days:
        return DAY_NAMES_ABBREV[6]
    return training_days[-1]


def _matching_memory_ids(
    memories: Sequence[Dict[str, Any]],
    resolved_day: str,
) -> List[str]:
    ids: List[str] = []
    normalized_day = str(resolved_day or "").strip().lower()
    for memory in memories or []:
        if not isinstance(memory, dict):
            continue
        text = str(memory.get("text") or "").lower()
        memory_type = memory.get("memory_type")
        memory_id = memory.get("id")
        if not memory_id:
            continue
        if memory_type == "long_run_day" and normalized_day in text:
            ids.append(str(memory_id))
    return ids


def resolve_long_run_day(
    plan_request: Dict[str, Any],
    hints: Sequence[str],
    memories: Sequence[Dict[str, Any]],
    training_days: Sequence[str],
) -> Tuple[str, DecisionReason]:
    user_preference = plan_request.get("long_run_day")
    if user_preference and user_preference in training_days:
        return user_preference, DecisionReason(
            field="long_run_day",
            value=user_preference,
            source="user_input",
            rationale="Used explicit long_run_day from plan_request.",
        )

    inferred = infer_long_run_day_from_memory_hints(hints or [], training_days or [])
    if inferred:
        memory_ids = _matching_memory_ids(memories or [], inferred)
        return inferred, DecisionReason(
            field="long_run_day",
            value=inferred,
            source="memory",
            memory_ids=memory_ids,
            rationale="Resolved from coach memory hints.",
        )

    fallback = _fallback_long_run_day(training_days or [])
    return fallback, DecisionReason(
        field="long_run_day",
        value=fallback,
        source="default_fallback",
        rationale="Auto-selected long_run_day using Sat > Sun > last training day.",
    )
