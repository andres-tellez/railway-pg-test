"""Structured ``updates`` merges from chips and tool payloads (Phase 7.1)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def apply_structured_updates(
    up: Dict[str, Any],
    *,
    draft: Dict[str, Any],
    ux: Dict[str, Any],
    alignment: Dict[str, Any],
    alignment_answers: Dict[str, Any],
    errors: List[str],
    prior_training_days_for_expansion: Optional[List[str]],
) -> None:
    from src.smartcoach_mobile_coach import plan_intake_flow as pif

    for key, raw in up.items():
        if key == "race_date":
            nd = pif._parse_race_date_natural_language(raw)
            if nd is None:
                errors.append(
                    "race_date must be a real calendar day "
                    "(e.g. 2026-10-11 or October 11, 2026)."
                )
            else:
                draft["race_date"] = nd
        elif key == "race_distance":
            if isinstance(raw, str) and raw.strip():
                draft["race_distance"] = pif._normalize_race_distance_intake(raw)
            else:
                errors.append("race_distance must be a non-empty string.")
        elif key == "race_name":
            if raw is None:
                draft.pop("race_name", None)
            elif isinstance(raw, str):
                draft["race_name"] = raw.strip()[:255]
            else:
                errors.append("race_name must be a string.")
        elif key == "race_location":
            if raw is None:
                draft.pop("race_location", None)
            elif isinstance(raw, str):
                draft["race_location"] = raw.strip()[:255]
            else:
                errors.append("race_location must be a string.")
        elif key == "primary_goal":
            ng = pif._normalize_goal(raw)
            if ng is None:
                errors.append("primary_goal must be 'Just Finish' or 'Target Time'.")
            else:
                draft["primary_goal"] = ng
        elif key == "target_time":
            if raw is None:
                draft.pop("target_time", None)
            elif isinstance(raw, str) and raw.strip():
                draft["target_time"] = pif._normalize_target_time_phrase(raw.strip())
            else:
                errors.append("target_time must be a non-empty string when provided.")
        elif key == "training_days":
            ndays = pif._normalize_training_days(raw)
            if ndays is None:
                day_count = pif._extract_training_days_count(raw)
                if day_count is not None:
                    ux["training_days_count"] = day_count
                    draft.pop("training_days", None)
                else:
                    errors.append(
                        "training_days must be weekdays or ranges (e.g. Monday through Saturday, "
                        "weekdays), abbreviations, or comma-separated lists."
                    )
            else:
                draft["training_days"] = ndays
                ux.pop("training_days_count", None)
        elif key == "long_run_day":
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                draft.pop("long_run_day", None)
            else:
                nd = pif._normalize_day(raw)
                if nd is None:
                    errors.append("long_run_day must be a valid weekday.")
                else:
                    draft["long_run_day"] = nd
        elif key in ("notes", "plan_name", "user_timezone"):
            if raw is None:
                draft.pop(key, None)
            elif isinstance(raw, str):
                draft[key] = raw.strip()
            else:
                errors.append(f"{key} must be a string.")
        elif key == "alignment_frequency_flexible":
            v = pif._normalize_alignment_bool(raw)
            if v is None:
                errors.append("alignment_frequency_flexible must be boolean-like.")
            else:
                alignment_answers["frequency_flexible"] = v
        elif key == "alignment_posture_priority":
            v = pif._normalize_alignment_posture(raw)
            if v is None:
                errors.append(
                    "alignment_posture_priority must be one of performance, balanced, durability."
                )
            else:
                alignment_answers["posture_priority"] = v
        elif key == "alignment_timeline_flexible":
            v = pif._normalize_alignment_bool(raw)
            if v is None:
                errors.append("alignment_timeline_flexible must be boolean-like.")
            else:
                alignment_answers["timeline_flexible"] = v
        elif key == "alignment_question_asked_category":
            if isinstance(raw, str) and raw.strip():
                category = raw.strip()
                asked = [
                    str(x)
                    for x in list(alignment.get("asked_categories") or [])
                    if isinstance(x, str)
                ]
                asked.append(category)
                alignment["asked_categories"] = asked
                alignment["question_count"] = len(asked)
            else:
                errors.append(
                    "alignment_question_asked_category must be a non-empty string."
                )
        elif key == "schedule_days_confirmed":
            v = pif._normalize_alignment_bool(raw)
            if v is None:
                errors.append("schedule_days_confirmed must be boolean-like.")
            elif v is True:
                ux.pop("schedule_confirm_before_posture", None)
            else:
                ux.pop("schedule_confirm_before_posture", None)
                ux["training_days_expansion_pending"] = True
                draft.pop("training_days", None)
                ux.pop("training_days_count", None)
        elif key == "plan_generation_confirmed":
            pass
        elif key == "apply_coach_suggested_goal":
            # Intake soft-reset only; flag is read from ``up`` in soft_reset (not on draft).
            pass
        elif key == "runner_tradeoff_choice":
            choice = str(raw or "").strip().lower()
            if choice == "continue_tradeoff":
                ux["runner_tradeoff_resolved"] = True
                ux.pop("runner_tradeoff_edit_focus", None)
            elif choice == "expand_running_days":
                ux["runner_tradeoff_resolved"] = True
                ux.pop("runner_tradeoff_edit_focus", None)
                ux["training_days_expansion_pending"] = True
                ux["runner_add_day_pick_pending"] = True
                if isinstance(prior_training_days_for_expansion, list):
                    ux["expansion_base_training_days"] = list(
                        prior_training_days_for_expansion
                    )
                draft.pop("training_days", None)
                ux.pop("training_days_count", None)
            elif choice == "adjust_goal":
                ux["runner_tradeoff_edit_focus"] = "goal"
                ux["runner_goal_edit_pending"] = True
                ux.pop("plan_generation_confirmed", None)
            elif choice == "adjust_timeline":
                ux["runner_tradeoff_edit_focus"] = "timeline"
            elif choice == "build_base_first":
                ux["runner_tradeoff_edit_focus"] = "base"
