"""
Deterministic intake-alignment state evaluator for high-tension plan intake.

This module is intentionally narrow and read-only:
- no planner imports
- no load/volume computation
- no hidden heuristics
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_POSTURE_VALUES = frozenset({"PERFORMANCE_LEANING", "BALANCED", "DURABILITY_FIRST"})

_CORE_CATEGORIES = ("frequency_flexibility", "posture_priority")
_OPTIONAL_CATEGORIES = ("timeline_flexibility",)
_MAX_QUESTIONS = 3


def _normalize_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("yes", "y", "true", "1"):
            return True
        if s in ("no", "n", "false", "0"):
            return False
    return None


def _normalize_posture(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    if not s:
        return None
    aliases = {
        "performance": "PERFORMANCE_LEANING",
        "performance_leaning": "PERFORMANCE_LEANING",
        "balanced": "BALANCED",
        "durability": "DURABILITY_FIRST",
        "durability_first": "DURABILITY_FIRST",
    }
    normalized = aliases.get(s)
    if normalized in _POSTURE_VALUES:
        return normalized
    return None


def evaluate_intake_alignment_state(
    *,
    ambition_stance: str,
    primary_goal: Optional[str],
    frequency_flexible: Any = None,
    posture_priority: Any = None,
    timeline_flexible: Any = None,
    question_count: int = 0,
) -> Dict[str, Any]:
    """
    Build deterministic alignment state used by pre-generation checkpoint.
    """
    attributions: List[str] = []
    unresolved_flags: List[str] = []
    allowed_question_categories: List[str] = []

    fq = max(0, int(question_count or 0))
    if fq > _MAX_QUESTIONS:
        fq = _MAX_QUESTIONS

    goal = (primary_goal or "").strip().lower()
    is_target_time_goal = goal == "target time"

    pause_required = is_target_time_goal and ambition_stance in (
        "HIGH_TENSION",
        "MANAGEABLE_TENSION",
    )
    if pause_required:
        attributions.append("RULE_ALIGNMENT_PAUSE_REQUIRED_FOR_TENSION")
    else:
        attributions.append("RULE_ALIGNMENT_NO_PAUSE_REQUIRED")

    freq_flexible = _normalize_bool(frequency_flexible)
    posture = _normalize_posture(posture_priority)
    timeline = _normalize_bool(timeline_flexible)

    if pause_required:
        if freq_flexible is None:
            unresolved_flags.append("frequency_flexibility")
        if posture is None:
            unresolved_flags.append("posture_priority")
        if (
            ambition_stance == "HIGH_TENSION"
            and freq_flexible is False
            and timeline is None
            and "frequency_flexibility" not in unresolved_flags
        ):
            unresolved_flags.append("timeline_flexibility")

    if not pause_required:
        posture_state = "BALANCED"
    elif posture is not None:
        posture_state = posture
    elif fq >= _MAX_QUESTIONS:
        posture_state = "BALANCED"
        unresolved_flags = []
        attributions.append("RULE_ALIGNMENT_QUESTION_CAP_REACHED")
    else:
        posture_state = "UNRESOLVED"

    if pause_required and fq < _MAX_QUESTIONS:
        for category in _CORE_CATEGORIES:
            if category in unresolved_flags:
                allowed_question_categories.append(category)
        for category in _OPTIONAL_CATEGORIES:
            if category in unresolved_flags:
                allowed_question_categories.append(category)
        # Bounded list in deterministic order.
        allowed_question_categories = allowed_question_categories[:3]
    else:
        allowed_question_categories = []

    generation_ready = (not pause_required) or len(unresolved_flags) == 0
    if generation_ready:
        attributions.append("RULE_ALIGNMENT_READY_TO_PROCEED")
    else:
        attributions.append("RULE_ALIGNMENT_NOT_READY")

    return {
        "pause_required": pause_required,
        "posture_state": posture_state,
        "unresolved_flags": unresolved_flags,
        "allowed_question_categories": allowed_question_categories,
        "generation_ready": generation_ready,
        "attributions": attributions,
        "question_count": fq,
    }
