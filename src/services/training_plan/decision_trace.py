from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from src.services.coach.user_plan_memory_service import (
    infer_long_run_day_from_memory_hints,
)
from src.smartcoach_mobile_coach.plan_intake_flow import _normalize_training_days
from src.utils.date_helpers import DAY_NAMES_ABBREV, DEFAULT_TRAINING_DAYS

DecisionSource = Literal["user_input", "memory", "default_fallback"]
logger = logging.getLogger(__name__)


@dataclass
class DecisionReason:
    field: str
    value: Any
    source: DecisionSource
    memory_ids: List[str] = field(default_factory=list)
    rationale: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _log_decision(reason: DecisionReason) -> None:
    logger.info(
        "[decision_trace] %s",
        json.dumps(
            {
                "field": reason.field,
                "value": reason.value,
                "source": reason.source,
                "memory_ids": reason.memory_ids,
            },
            sort_keys=True,
        ),
    )


def _validated_reason(reason: DecisionReason) -> DecisionReason:
    if reason.source == "memory":
        if not reason.memory_ids:
            raise ValueError("memory decision_trace entries must include memory_ids")
    else:
        reason.memory_ids = []
    _log_decision(reason)
    return reason


def _fallback_training_days() -> List[str]:
    return list(DEFAULT_TRAINING_DAYS)


def _fallback_long_run_day(training_days: Sequence[str]) -> str:
    if not training_days:
        raise ValueError("training_days must not be empty")
    if DAY_NAMES_ABBREV[5] in training_days:
        return DAY_NAMES_ABBREV[5]
    if DAY_NAMES_ABBREV[6] in training_days:
        return DAY_NAMES_ABBREV[6]
    return training_days[-1]


def _matching_long_run_memory_ids(
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
    return sorted(set(ids))


_WEEKDAY_TOKEN_RE = re.compile(
    r"\b(mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)s?\b",
    re.IGNORECASE,
)


def _extract_training_days_from_text(text: Any) -> Optional[List[str]]:
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None
    normalized = _normalize_training_days(raw)
    if normalized:
        return normalized
    tokens = _WEEKDAY_TOKEN_RE.findall(raw)
    if not tokens:
        return None
    return _normalize_training_days(tokens)


def _matching_training_days_memory_ids(
    memories: Sequence[Dict[str, Any]],
    resolved_days: Sequence[str],
) -> List[str]:
    expected = list(resolved_days or [])
    ids: List[str] = []
    for memory in memories or []:
        if not isinstance(memory, dict):
            continue
        if memory.get("memory_type") != "training_days":
            continue
        memory_id = memory.get("id")
        if not memory_id:
            continue
        parsed = _extract_training_days_from_text(memory.get("text"))
        if parsed == expected:
            ids.append(str(memory_id))
    return sorted(set(ids))


def _resolve_training_days_from_memories(
    memories: Sequence[Dict[str, Any]],
) -> Tuple[Optional[List[str]], List[str]]:
    prioritized = sorted(
        [memory for memory in memories or [] if isinstance(memory, dict)],
        key=lambda memory: 0 if memory.get("memory_type") == "training_days" else 1,
    )
    for memory in prioritized:
        if memory.get("memory_type") != "training_days":
            continue
        resolved = _extract_training_days_from_text(memory.get("text"))
        if not resolved:
            continue
        memory_ids = _matching_training_days_memory_ids(memories, resolved)
        if memory_ids:
            return resolved, memory_ids
    return None, []


def _has_training_days_memory_without_resolved_value(
    hints: Sequence[str],
    memories: Sequence[Dict[str, Any]],
) -> bool:
    for memory in memories or []:
        if not isinstance(memory, dict):
            continue
        if memory.get("memory_type") != "training_days":
            continue
        if str(memory.get("text") or "").strip():
            return _extract_training_days_from_text(memory.get("text")) is None
    return any(
        "days per week" in str(hint).lower() or "training days" in str(hint).lower()
        for hint in hints or []
    )


def _memory_day_outside_training_days(
    hints: Sequence[str],
    memories: Sequence[Dict[str, Any]],
    training_days: Sequence[str],
) -> bool:
    allowed_days = {str(day) for day in training_days or []}
    for day_name, abbrev in (
        ("saturday", "Sat"),
        ("sunday", "Sun"),
        ("monday", "Mon"),
        ("tuesday", "Tue"),
        ("wednesday", "Wed"),
        ("thursday", "Thu"),
        ("friday", "Fri"),
    ):
        if abbrev in allowed_days:
            continue
        if any(
            day_name in str(memory.get("text") or "").lower()
            for memory in memories or []
            if isinstance(memory, dict) and memory.get("memory_type") == "long_run_day"
        ):
            return True
        if any(day_name in str(hint).lower() for hint in hints or []):
            return True
    return False


def resolve_training_days(
    plan_request: Dict[str, Any],
    hints: Sequence[str],
    memories: Sequence[Dict[str, Any]],
    requested_training_days: Optional[Sequence[str]],
) -> Tuple[List[str], DecisionReason]:
    explicit = plan_request.get("training_days")
    if isinstance(explicit, list) and explicit:
        value = [str(day) for day in explicit if str(day).strip()]
        if value:
            return value, _validated_reason(
                DecisionReason(
                    field="training_days",
                    value=value,
                    source="user_input",
                    rationale="user provided",
                )
            )

    if requested_training_days:
        value = [str(day) for day in requested_training_days if str(day).strip()]
        if value:
            return value, _validated_reason(
                DecisionReason(
                    field="training_days",
                    value=value,
                    source="user_input",
                    rationale="user provided",
                )
            )

    inferred, memory_ids = _resolve_training_days_from_memories(memories or [])
    if inferred and memory_ids:
        return inferred, _validated_reason(
            DecisionReason(
                field="training_days",
                value=inferred,
                source="memory",
                memory_ids=memory_ids,
                rationale="derived from user memory",
            )
        )

    rationale = "default selection (Mon, Wed, Thu, Sat)"
    if _has_training_days_memory_without_resolved_value(hints or [], memories or []):
        rationale = "memory not actionable for weekdays, using fallback"
    fallback = _fallback_training_days()
    return fallback, _validated_reason(
        DecisionReason(
            field="training_days",
            value=fallback,
            source="default_fallback",
            rationale=rationale,
        )
    )


def resolve_long_run_day(
    plan_request: Dict[str, Any],
    hints: Sequence[str],
    memories: Sequence[Dict[str, Any]],
    training_days: Sequence[str],
) -> Tuple[str, DecisionReason]:
    user_preference = plan_request.get("long_run_day")
    if user_preference and user_preference in training_days:
        return user_preference, _validated_reason(
            DecisionReason(
                field="long_run_day",
                value=user_preference,
                source="user_input",
                rationale="user provided",
            )
        )

    inferred = infer_long_run_day_from_memory_hints(hints or [], training_days or [])
    if inferred:
        memory_ids = _matching_long_run_memory_ids(memories or [], inferred)
        return inferred, _validated_reason(
            DecisionReason(
                field="long_run_day",
                value=inferred,
                source="memory",
                memory_ids=memory_ids,
                rationale="derived from user memory",
            )
        )

    fallback = _fallback_long_run_day(training_days or [])
    rationale = "default selection (Sat > Sun > last)"
    if _memory_day_outside_training_days(
        hints or [], memories or [], training_days or []
    ):
        rationale = "memory value not in training_days, using fallback"
    return fallback, _validated_reason(
        DecisionReason(
            field="long_run_day",
            value=fallback,
            source="default_fallback",
            rationale=rationale,
        )
    )
