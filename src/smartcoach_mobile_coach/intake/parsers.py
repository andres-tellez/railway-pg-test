"""Natural-language fills layered after structured ``updates`` (Phase 7.1)."""

from __future__ import annotations

from typing import Any, Dict, Optional


def apply_natural_language_fills(
    *,
    draft: Dict[str, Any],
    ux: Dict[str, Any],
    alignment_answers: Dict[str, Any],
    prior_alignment_answers: Dict[str, Any],
    source_user_message: Optional[str],
    skip_nl_core: bool,
) -> None:
    """Infer draft + alignment fields from ``source_user_message`` when allowed."""
    from src.smartcoach_mobile_coach import plan_intake_flow as pif

    if not skip_nl_core:
        rd_cur = draft.get("race_distance")
        if not (isinstance(rd_cur, str) and rd_cur.strip()):
            msg_rd = pif._try_infer_race_distance((source_user_message or "").strip())
            if msg_rd:
                draft["race_distance"] = msg_rd

        pif._fill_race_date_from_user_message(draft, source_user_message)

        pif._fill_primary_goal_from_user_message(draft, source_user_message)

        pif._fill_goal_time_from_user_message(draft, source_user_message)

        pif._fill_training_days_from_user_message(draft, ux, source_user_message)

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

    if (
        not skip_nl_core
        and "training_days" not in draft
        and "training_days_count" not in ux
    ):
        day_count = pif._extract_training_days_count(source_user_message)
        if day_count is not None:
            ux["training_days_count"] = day_count

    pif._fill_race_distance_from_named_event(draft)
    pif._fill_race_name_from_user_text(draft, source_user_message)

    pif._auto_fill_long_run_day(draft)
