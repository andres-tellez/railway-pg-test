"""Auxiliary NL fills after structured ``updates`` (non-core fields only)."""

from __future__ import annotations

from typing import Any, Dict, Optional


def apply_natural_language_fills(
    *,
    draft: Dict[str, Any],
    ux: Dict[str, Any],
    alignment_answers: Dict[str, Any],
    prior_alignment_answers: Dict[str, Any],
    source_user_message: Optional[str],
) -> None:
    """Infer alignment and auxiliary draft fields from ``source_user_message``."""
    from src.smartcoach_mobile_coach import plan_intake_flow as pif

    msg_alignment_answers = pif._extract_alignment_answers_from_user_message(
        source_user_message
    )
    if msg_alignment_answers:
        for key, value in msg_alignment_answers.items():
            if key not in alignment_answers:
                alignment_answers[key] = value

    if (
        alignment_answers.get("frequency_flexible") is True
        and prior_alignment_answers.get("frequency_flexible") is not True
    ):
        ux["training_days_expansion_pending"] = True

    pif._fill_race_distance_from_named_event(draft)
    pif._fill_race_name_from_user_text(draft, source_user_message)

    pif._auto_fill_long_run_day(draft)
