"""
Plan creation UX: explicit phase + single resolver for structured chips.

``ux.plan_creation_phase`` is the source of truth when split-confirm is enabled.
Legacy ``runner_tradeoff_*`` flags are derived for backward compatibility.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.smartcoach_mobile_coach.plan_intake_flow import (
    build_core_structured_ui_prompt,
    plan_creation_split_confirm_enabled,
)
from src.utils.date_helpers import DAY_NAMES_ABBREV

# --- Phase constants (v1; split-confirm path only) ---

PHASE_COLLECTING_INTAKE = "collecting_intake"
PHASE_AWAITING_INTAKE_CONFIRMATION = "awaiting_intake_confirmation"
PHASE_AWAITING_TRADEOFF_CHOICE = "awaiting_tradeoff_choice"
PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY = "collecting_additional_training_day"
PHASE_COLLECTING_GOAL_ADJUSTMENT = "collecting_goal_adjustment"
PHASE_COLLECTING_TIMELINE_ADJUSTMENT = "collecting_timeline_adjustment"
PHASE_AWAITING_PLAN_GENERATION_CONFIRMATION = "awaiting_plan_generation_confirmation"
PHASE_GENERATED = "generated"

_PLAN_CREATION_PHASES = frozenset(
    {
        PHASE_COLLECTING_INTAKE,
        PHASE_AWAITING_INTAKE_CONFIRMATION,
        PHASE_AWAITING_TRADEOFF_CHOICE,
        PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY,
        PHASE_COLLECTING_GOAL_ADJUSTMENT,
        PHASE_COLLECTING_TIMELINE_ADJUSTMENT,
        PHASE_AWAITING_PLAN_GENERATION_CONFIRMATION,
        PHASE_GENERATED,
    }
)

_WEEKDAY_CHIP_LABELS = {
    "Mon": "Monday",
    "Tue": "Tuesday",
    "Wed": "Wednesday",
    "Thu": "Thursday",
    "Fri": "Friday",
    "Sat": "Saturday",
    "Sun": "Sunday",
}


def _merge_base_training_days_with_one(base: List[str], add: str) -> List[str]:
    s = {str(d) for d in base if isinstance(d, str)}
    s.add(str(add).strip())
    return [d for d in DAY_NAMES_ABBREV if d in s]


def _alignment_ui_prompt(intake_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    if ux.get("schedule_confirm_before_posture"):
        return None
    if ux.get("training_days_expansion_pending"):
        return None
    alignment = intake_state.get("alignment")
    if not isinstance(alignment, dict):
        return None
    st = alignment.get("state")
    if not isinstance(st, dict):
        return None
    if not st.get("pause_required") or st.get("generation_ready"):
        return None
    allowed = st.get("allowed_question_categories") or []
    first = (
        allowed[0]
        if isinstance(allowed, list) and allowed and isinstance(allowed[0], str)
        else ""
    )
    if first == "frequency_flexibility":
        return {
            "version": 1,
            "field_key": "alignment.frequency_flexible",
            "control_type": "single_select_chips",
            "selection_mode": "single",
            "required": True,
            "prompt": "Would you be open to adding one run day to support this goal?",
            "options": [
                {
                    "id": "frequency_fixed",
                    "label": "Keep schedule fixed",
                    "user_message": "Keep my current days fixed.",
                    "updates": {"alignment_frequency_flexible": False},
                },
                {
                    "id": "frequency_open",
                    "label": "Open to adding a day",
                    "user_message": "I can add one day.",
                    "updates": {"alignment_frequency_flexible": True},
                },
            ],
        }
    return None


def _schedule_confirmation_ui_prompt(
    intake_state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    if not ux.get("schedule_confirm_before_posture"):
        return None
    draft = (
        intake_state.get("draft") if isinstance(intake_state.get("draft"), dict) else {}
    )
    days = draft.get("training_days")
    if not isinstance(days, list) or not days:
        return None
    day_preview = ", ".join(str(d) for d in days if isinstance(d, str))
    return {
        "version": 1,
        "field_key": "plan_intake.schedule_confirmation",
        "control_type": "single_select_chips",
        "selection_mode": "single",
        "required": True,
        "prompt": (
            f"You'll train on {day_preview}. Does this weekly schedule look right?"
        ),
        "options": [
            {
                "id": "sched_yes",
                "label": "Yes",
                "user_message": "Yes, that weekly schedule looks right.",
                "updates": {"schedule_days_confirmed": True},
            },
            {
                "id": "sched_no",
                "label": "No, change days",
                "user_message": "I'd like to change my training days.",
                "updates": {"schedule_days_confirmed": False},
            },
        ],
    }


def _additional_training_day_ui_prompt(
    intake_state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not plan_creation_split_confirm_enabled():
        return None
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    if not ux.get("runner_add_day_pick_pending"):
        return None
    if not ux.get("training_days_expansion_pending"):
        return None
    base = ux.get("expansion_base_training_days")
    if not isinstance(base, list) or not base:
        return None
    missing = [
        m for m in (intake_state.get("missing_required") or []) if isinstance(m, str)
    ]
    if "training_days" not in missing:
        return None
    existing = {str(d) for d in base if isinstance(d, str)}
    candidates = [d for d in DAY_NAMES_ABBREV if d not in existing]
    if not candidates:
        return None
    options: List[Dict[str, Any]] = []
    for d in candidates:
        merged = _merge_base_training_days_with_one(base, d)
        label = _WEEKDAY_CHIP_LABELS.get(d, d)
        day_list = ", ".join(merged)
        options.append(
            {
                "id": f"add_day_{d.lower()}",
                "label": label,
                "user_message": (
                    f"I'd like to add {label} — my training days should be {day_list}."
                ),
                "updates": {"training_days": merged},
            }
        )
    return {
        "version": 1,
        "field_key": "plan_intake.collect_additional_training_day",
        "control_type": "single_select_chips",
        "selection_mode": "single",
        "required": True,
        "prompt": "Which additional day would you like to include?",
        "options": options,
    }


def _runner_tradeoff_ui_prompt(
    intake_state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not plan_creation_split_confirm_enabled():
        return None
    if not intake_state.get("ready_to_generate"):
        return None
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    if ux.get("schedule_confirm_before_posture"):
        return None
    if ux.get("training_days_expansion_pending"):
        return None
    if not ux.get("intake_confirmed") or not ux.get("runner_review_delivered"):
        return None
    if ux.get("plan_creation_phase") != PHASE_AWAITING_TRADEOFF_CHOICE:
        return None
    return {
        "version": 1,
        "field_key": "plan_intake.runner_tradeoff",
        "control_type": "single_select_chips",
        "selection_mode": "single",
        "required": True,
        "prompt": "A few options before we build your plan:",
        "options": [
            {
                "id": "rt_expand",
                "label": "Add another training day",
                "user_message": (
                    "I'd like to add another training day — let's adjust my training days."
                ),
                "updates": {"runner_tradeoff_choice": "expand_running_days"},
            },
            {
                "id": "rt_goal",
                "label": "Adjust my marathon goal",
                "user_message": "I want to change my marathon goal or target time.",
                "updates": {"runner_tradeoff_choice": "adjust_goal"},
            },
            {
                "id": "rt_time",
                "label": "Move my goal race farther out",
                "user_message": (
                    "I want more time before my race — let's adjust my goal race date."
                ),
                "updates": {"runner_tradeoff_choice": "adjust_timeline"},
            },
            {
                "id": "rt_continue",
                "label": "Keep the current goal and schedule",
                "user_message": (
                    "Let's keep my current goal and weekly schedule and move on to building the plan."
                ),
                "updates": {"runner_tradeoff_choice": "continue_tradeoff"},
            },
        ],
    }


def _plan_generation_confirm_ui_prompt(
    intake_state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not plan_creation_split_confirm_enabled():
        return None
    if not intake_state.get("ready_to_generate"):
        return None
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    if ux.get("plan_creation_phase") != PHASE_AWAITING_PLAN_GENERATION_CONFIRMATION:
        return None
    if not ux.get("intake_confirmed") or not ux.get("runner_review_delivered"):
        return None
    if ux.get("plan_generation_confirmed"):
        return None
    if ux.get("runner_review_assessment_status") == "needs_more_info":
        return None
    if ux.get("runner_tradeoff_edit_focus") in ("goal", "timeline"):
        return None
    return {
        "version": 1,
        "field_key": "plan_intake.plan_generation_confirm",
        "control_type": "single_select_chips",
        "selection_mode": "single",
        "required": True,
        "prompt": "When you’re ready, create your training plan.",
        "options": [
            {
                "id": "create_plan",
                "label": "Create my plan",
                "user_message": "Create my plan",
                "updates": {"plan_generation_confirmed": True},
            },
        ],
    }


def recompute_plan_creation_phase(state: Dict[str, Any]) -> None:
    """
    Set ``ux.plan_creation_phase`` from draft, readiness, alignment, and review hints.

    Call after ``update_plan_intake_state`` builds ``state`` and after orchestrator
    stamps ``runner_review_assessment_status``.
    """
    if not plan_creation_split_confirm_enabled():
        return
    ux = state.get("ux") if isinstance(state.get("ux"), dict) else {}
    if (
        state.get("status") == "generated"
        or ux.get("plan_creation_phase") == PHASE_GENERATED
    ):
        ux["plan_creation_phase"] = PHASE_GENERATED
        state["ux"] = ux
        return

    missing = [m for m in (state.get("missing_required") or []) if isinstance(m, str)]
    if (
        ux.get("runner_add_day_pick_pending")
        and ux.get("training_days_expansion_pending")
        and "training_days" in missing
    ):
        ux["plan_creation_phase"] = PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY
        state["ux"] = ux
        return

    ready = bool(state.get("ready_to_generate"))
    ra = str(ux.get("runner_review_assessment_status") or "").strip()

    if not ready:
        ux["plan_creation_phase"] = PHASE_COLLECTING_INTAKE
        state["ux"] = ux
        return

    if not ux.get("intake_confirmed"):
        ux["plan_creation_phase"] = PHASE_AWAITING_INTAKE_CONFIRMATION
        state["ux"] = ux
        return

    if not ux.get("runner_review_delivered"):
        # Runner-review API not merged onto this snapshot yet (orchestrator stamps next).
        ux["plan_creation_phase"] = PHASE_COLLECTING_INTAKE
        state["ux"] = ux
        return

    if ux.get("runner_tradeoff_edit_focus") == "goal":
        ux["plan_creation_phase"] = PHASE_COLLECTING_GOAL_ADJUSTMENT
        state["ux"] = ux
        return
    if ux.get("runner_tradeoff_edit_focus") == "timeline":
        ux["plan_creation_phase"] = PHASE_COLLECTING_TIMELINE_ADJUSTMENT
        state["ux"] = ux
        return

    if ra == "needs_more_info":
        ux["plan_creation_phase"] = PHASE_COLLECTING_INTAKE
        state["ux"] = ux
        return

    if ra == "needs_user_decision" and not ux.get("runner_tradeoff_resolved"):
        ux["plan_creation_phase"] = PHASE_AWAITING_TRADEOFF_CHOICE
        state["ux"] = ux
        return

    ux["plan_creation_phase"] = PHASE_AWAITING_PLAN_GENERATION_CONFIRMATION
    state["ux"] = ux


def sync_legacy_ux_from_phase(ux: Dict[str, Any], phase: Optional[str]) -> None:
    """Mirror ``plan_creation_phase`` into legacy flags for one release."""
    if not plan_creation_split_confirm_enabled():
        return
    if not phase or phase not in _PLAN_CREATION_PHASES:
        return
    ux["runner_tradeoff_pending"] = phase == PHASE_AWAITING_TRADEOFF_CHOICE
    if phase in (
        PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY,
        PHASE_COLLECTING_GOAL_ADJUSTMENT,
        PHASE_COLLECTING_TIMELINE_ADJUSTMENT,
        PHASE_GENERATED,
    ):
        ux["runner_tradeoff_resolved"] = True
    elif phase == PHASE_AWAITING_TRADEOFF_CHOICE:
        ux["runner_tradeoff_resolved"] = False
    elif phase == PHASE_AWAITING_PLAN_GENERATION_CONFIRMATION:
        ra = str(ux.get("runner_review_assessment_status") or "")
        if ra != "needs_user_decision":
            ux["runner_tradeoff_resolved"] = True
    else:
        ux["runner_tradeoff_resolved"] = False


def apply_review_to_plan_intake_ux_for_phase(
    state: Dict[str, Any],
    runner_review_api: Optional[Dict[str, Any]],
    *,
    intake_confirmed: bool,
) -> None:
    """
    Stamp review-derived UX and recompute phase (orchestrator outbound path).

    Replaces ad-hoc boolean merge logic.
    """
    if not plan_creation_split_confirm_enabled():
        return
    uxs = state.get("ux")
    if not isinstance(uxs, dict):
        uxs = {}
        state["ux"] = uxs
    if intake_confirmed:
        uxs["runner_review_delivered"] = True
    if runner_review_api is not None:
        ra = str(runner_review_api.get("assessment_status") or "")
        prev_ra = str(uxs.get("runner_review_assessment_status") or "")
        uxs["runner_review_assessment_status"] = ra
        tradeoff_ok = bool(uxs.get("runner_tradeoff_resolved"))
        if ra == "needs_user_decision":
            if prev_ra == "ready_to_generate" and tradeoff_ok:
                uxs["runner_tradeoff_resolved"] = False
        elif ra == "needs_more_info":
            if not tradeoff_ok:
                uxs["runner_tradeoff_resolved"] = False
    recompute_plan_creation_phase(state)
    sync_legacy_ux_from_phase(uxs, str(uxs.get("plan_creation_phase") or ""))


def compute_plan_creation_ui(
    intake_state: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Single entry point for plan-creation structured chips (split-confirm on).

    When split-confirm is off, alignment + core intake only (legacy).
    """
    if not isinstance(intake_state, dict):
        return None

    align = _alignment_ui_prompt(intake_state)
    if align is not None:
        return align

    if not plan_creation_split_confirm_enabled():
        return build_core_structured_ui_prompt(intake_state)

    sched = _schedule_confirmation_ui_prompt(intake_state)
    if sched is not None:
        return sched

    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    phase = str(ux.get("plan_creation_phase") or "")

    if phase == PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY:
        add_day = _additional_training_day_ui_prompt(intake_state)
        if add_day is not None:
            return add_day

    if phase == PHASE_AWAITING_TRADEOFF_CHOICE:
        tradeoff = _runner_tradeoff_ui_prompt(intake_state)
        if tradeoff is not None:
            return tradeoff

    if phase == PHASE_AWAITING_PLAN_GENERATION_CONFIRMATION:
        gen_chip = _plan_generation_confirm_ui_prompt(intake_state)
        if gen_chip is not None:
            return gen_chip

    if phase in (
        PHASE_COLLECTING_INTAKE,
        PHASE_COLLECTING_GOAL_ADJUSTMENT,
        PHASE_COLLECTING_TIMELINE_ADJUSTMENT,
    ):
        return build_core_structured_ui_prompt(intake_state)

    if phase == PHASE_AWAITING_INTAKE_CONFIRMATION:
        return None
    if phase == PHASE_GENERATED:
        return None

    return build_core_structured_ui_prompt(intake_state)
