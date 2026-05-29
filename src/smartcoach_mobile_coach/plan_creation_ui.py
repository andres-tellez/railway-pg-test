"""
Plan creation UX: explicit phase + single resolver for structured chips.

``ux.plan_creation_phase`` is the source of truth when split-confirm is enabled.
Legacy ``runner_tradeoff_*`` flags are derived for backward compatibility.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.smartcoach_mobile_coach.hr_calibration_intake import (
    build_plan_profile_hr_beat_ui_prompt,
    plan_profile_hr_beat_ui_active,
    sync_plan_profile_hr_beat_ux,
)
from src.smartcoach_mobile_coach.plan_intake_flow import (
    build_core_structured_ui_prompt,
    plan_creation_split_confirm_enabled,
)
from src.schemas.plan_schema import PrimaryGoal
from src.coaching_intelligence.time_clock import (
    format_clock_seconds,
    parse_clock_seconds,
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

_GOAL_ADJUST_MIN_SEC = 2 * 3600 + 45 * 60  # 2:45:00
_GOAL_ADJUST_MAX_SEC = 6 * 3600  # 6:00:00


def _short_marathon_clock_label(clock: str) -> str:
    sec = parse_clock_seconds(clock)
    if sec is None:
        return clock.strip()
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}"
    return f"{m}:{s:02d}"


def _round_clock_sec_to_5min(sec: int) -> int:
    return int(round(sec / 300.0)) * 300


def _goal_time_options_from_proposed_clock(proposed_clock: str) -> List[Dict[str, Any]]:
    """Time-target chips bracketing policy ``adjust_goal.proposed_value`` (≈−10m / +15m)."""
    center0 = parse_clock_seconds(proposed_clock)
    if center0 is None:
        return []
    center = _round_clock_sec_to_5min(
        max(_GOAL_ADJUST_MIN_SEC, min(_GOAL_ADJUST_MAX_SEC, center0))
    )
    faster = _round_clock_sec_to_5min(center - 600)
    slower = _round_clock_sec_to_5min(center + 900)
    faster = max(_GOAL_ADJUST_MIN_SEC, min(_GOAL_ADJUST_MAX_SEC, faster))
    slower = max(_GOAL_ADJUST_MIN_SEC, min(_GOAL_ADJUST_MAX_SEC, slower))
    ordered: List[tuple[int, str]] = []
    seen: set[int] = set()
    for cand in (faster, center, slower):
        c = max(_GOAL_ADJUST_MIN_SEC, min(_GOAL_ADJUST_MAX_SEC, cand))
        if c in seen:
            continue
        seen.add(c)
        clock = format_clock_seconds(c)
        label = _short_marathon_clock_label(clock)
        ordered.append((c, label))
    options: List[Dict[str, Any]] = []
    for sec, label in ordered:
        clock = format_clock_seconds(sec)
        pid = f"ga_ev_{sec}"
        options.append(
            {
                "id": pid,
                "label": label,
                "user_message": f"I'm aiming for about {label} (finish ~{clock}).",
                "updates": {
                    "primary_goal": PrimaryGoal.TARGET_TIME.value,
                    "target_time": clock,
                },
            }
        )
    return options


def _adjust_goal_proposed_clock_from_ux(ux: Dict[str, Any]) -> Optional[str]:
    readiness = _plan_generation_readiness(ux)
    for row in readiness.get("suggestions") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("id") or "").strip() != "adjust_goal":
            continue
        pv = row.get("proposed_value")
        if pv is not None and str(pv).strip():
            return str(pv).strip()
    return None


def _plan_generation_readiness(ux: Dict[str, Any]) -> Dict[str, Any]:
    readiness = ux.get("plan_generation_readiness")
    return readiness if isinstance(readiness, dict) else {}


def _readiness_decision(ux: Dict[str, Any]) -> str:
    return str(_plan_generation_readiness(ux).get("decision") or "").strip()


def _readiness_level_is_insufficient_data(ux: Dict[str, Any]) -> bool:
    return (
        str(_plan_generation_readiness(ux).get("readiness_level") or "").strip()
        == "insufficient_data"
    )


def _readiness_allowed_actions(ux: Dict[str, Any]) -> List[str]:
    readiness = _plan_generation_readiness(ux)
    actions = readiness.get("allowed_user_actions")
    if not isinstance(actions, list):
        return []
    return [str(action) for action in actions if str(action or "").strip()]


def _readiness_allows_create_plan(ux: Dict[str, Any]) -> bool:
    readiness = _plan_generation_readiness(ux)
    if not readiness:
        return False
    return readiness.get("decision") == "allow"


def _option_allowed_by_readiness(
    ux: Dict[str, Any],
    action_aliases: List[str],
) -> bool:
    allowed = set(_readiness_allowed_actions(ux))
    if not allowed:
        return True
    return any(alias in allowed for alias in action_aliases)


def _merge_base_training_days_with_one(base: List[str], add: str) -> List[str]:
    s = {str(d) for d in base if isinstance(d, str)}
    s.add(str(add).strip())
    return [d for d in DAY_NAMES_ABBREV if d in s]


def _alignment_ui_prompt(intake_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    if plan_profile_hr_beat_ui_active(intake_state):
        return None
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
    if plan_profile_hr_beat_ui_active(intake_state):
        return None
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


def _goal_adjustment_ui_prompt(
    intake_state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Structured chips after user chooses **adjust goal** from runner review."""
    draft = (
        intake_state.get("draft") if isinstance(intake_state.get("draft"), dict) else {}
    )
    rd = str(draft.get("race_distance") or "").lower()
    if "marathon" not in rd or "half" in rd:
        return None
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    proposed = _adjust_goal_proposed_clock_from_ux(ux)
    finish_opt: Dict[str, Any] = {
        "id": "ga_finish",
        "label": "Finish strong (no time target)",
        "user_message": "I want to finish strong — no specific time goal.",
        "updates": {
            "primary_goal": PrimaryGoal.JUST_FINISH.value,
            "target_time": None,
        },
    }
    if proposed:
        time_options = _goal_time_options_from_proposed_clock(proposed)
    else:
        presets: List[tuple[str, str, str]] = [
            ("ga_tt300", "3:00", "3:00:00"),
            ("ga_tt315", "3:15", "3:15:00"),
            ("ga_tt330", "3:30", "3:30:00"),
            ("ga_tt340", "3:40", "3:40:00"),
            ("ga_tt345", "3:45", "3:45:00"),
            ("ga_tt400", "4:00", "4:00:00"),
            ("ga_tt430", "4:30", "4:30:00"),
            ("ga_tt500", "5:00", "5:00:00"),
        ]
        time_options = [
            {
                "id": pid,
                "label": label,
                "user_message": f"I'm aiming for about {label} (finish ~{clock}).",
                "updates": {
                    "primary_goal": PrimaryGoal.TARGET_TIME.value,
                    "target_time": clock,
                },
            }
            for pid, label, clock in presets
        ]
    return {
        "version": 1,
        "field_key": "plan_intake.goal_adjustment",
        "control_type": "single_select_chips",
        "selection_mode": "single",
        "required": True,
        "prompt": "What goal do you want to use for this race instead?",
        "options": [finish_opt, *time_options],
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
    options = [
        {
            "id": "rt_expand",
            "label": "Add another training day",
            "user_message": (
                "I'd like to add another training day — let's adjust my training days."
            ),
            "updates": {"runner_tradeoff_choice": "expand_running_days"},
            "_readiness_actions": ["add_running_day", "expand_running_days"],
        },
        {
            "id": "rt_goal",
            "label": "Adjust my marathon goal",
            "user_message": "I want to change my marathon goal or target time.",
            "updates": {"runner_tradeoff_choice": "adjust_goal"},
            "_readiness_actions": ["adjust_goal"],
        },
        {
            "id": "rt_time",
            "label": "Move my goal race farther out",
            "user_message": (
                "I want more time before my race — let's adjust my goal race date."
            ),
            "updates": {"runner_tradeoff_choice": "adjust_timeline"},
            "_readiness_actions": ["adjust_timeline"],
        },
        {
            "id": "rt_base",
            "label": "Build base first",
            "user_message": (
                "I want to build more base first before chasing this goal."
            ),
            "updates": {"runner_tradeoff_choice": "build_base_first"},
            "_readiness_actions": ["build_base_first"],
        },
        {
            "id": "rt_continue",
            "label": "Keep the current goal and schedule",
            "user_message": (
                "Let's keep my current goal and weekly schedule and move on to building the plan."
            ),
            "updates": {"runner_tradeoff_choice": "continue_tradeoff"},
            "_readiness_actions": ["continue_tradeoff", "continue_with_warning"],
        },
    ]
    filtered_options: List[Dict[str, Any]] = []
    for option in options:
        aliases = [
            str(alias)
            for alias in list(option.get("_readiness_actions") or [])
            if str(alias).strip()
        ]
        if _option_allowed_by_readiness(ux, aliases):
            cleaned = dict(option)
            cleaned.pop("_readiness_actions", None)
            filtered_options.append(cleaned)
    if not filtered_options:
        return None
    return {
        "version": 1,
        "field_key": "plan_intake.runner_tradeoff",
        "control_type": "single_select_chips",
        "selection_mode": "single",
        "required": True,
        "prompt": "A few options before we build your plan:",
        "options": filtered_options,
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
    if _readiness_level_is_insufficient_data(ux):
        return None
    if not _readiness_allows_create_plan(ux):
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

    if ux.get("runner_tradeoff_edit_focus") == "goal":
        ux["plan_creation_phase"] = PHASE_COLLECTING_GOAL_ADJUSTMENT
        state["ux"] = ux
        return
    if ux.get("runner_tradeoff_edit_focus") == "timeline":
        ux["plan_creation_phase"] = PHASE_COLLECTING_TIMELINE_ADJUSTMENT
        state["ux"] = ux
        return
    if ux.get("runner_tradeoff_edit_focus") == "base":
        ux["plan_creation_phase"] = PHASE_COLLECTING_GOAL_ADJUSTMENT
        state["ux"] = ux
        return

    if not ux.get("runner_review_delivered"):
        # Runner-review API not merged onto this snapshot yet (orchestrator stamps next).
        ux["plan_creation_phase"] = PHASE_COLLECTING_INTAKE
        state["ux"] = ux
        return

    if ra == "needs_user_decision" and _readiness_level_is_insufficient_data(ux):
        ux["plan_creation_phase"] = PHASE_COLLECTING_INTAKE
        state["ux"] = ux
        return

    readiness_decision = _readiness_decision(ux)
    if readiness_decision in ("defer", "block"):
        ux["plan_creation_phase"] = PHASE_AWAITING_TRADEOFF_CHOICE
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
        readiness = runner_review_api.get("plan_generation_readiness")
        if isinstance(readiness, dict):
            uxs["plan_generation_readiness"] = readiness
        tradeoff_ok = bool(uxs.get("runner_tradeoff_resolved"))
        if ra == "needs_user_decision":
            if prev_ra == "ready_to_generate" and tradeoff_ok:
                uxs["runner_tradeoff_resolved"] = False
            elif _readiness_level_is_insufficient_data(uxs):
                if not tradeoff_ok:
                    uxs["runner_tradeoff_resolved"] = False
    recompute_plan_creation_phase(state)
    sync_legacy_ux_from_phase(uxs, str(uxs.get("plan_creation_phase") or ""))


def compute_plan_creation_ui(
    intake_state: Optional[Dict[str, Any]],
    *,
    session: Any = None,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Single entry point for plan-creation structured chips (split-confirm on).

    When split-confirm is off, alignment + core intake only (legacy).
    When ``session`` and ``user_id`` are set, refreshes plan profile HR beat ux first.
    """
    if not isinstance(intake_state, dict):
        return None

    if session is not None and user_id:
        intake_state = sync_plan_profile_hr_beat_ux(session, str(user_id), intake_state)

    align = _alignment_ui_prompt(intake_state)
    if align is not None:
        return align

    if not plan_creation_split_confirm_enabled():
        hr_cal = build_plan_profile_hr_beat_ui_prompt(intake_state)
        if hr_cal is not None:
            return hr_cal
        return build_core_structured_ui_prompt(intake_state)

    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    phase = str(ux.get("plan_creation_phase") or "")

    if phase == PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY:
        add_day = _additional_training_day_ui_prompt(intake_state)
        if add_day is not None:
            return add_day

    if phase == PHASE_COLLECTING_GOAL_ADJUSTMENT:
        ga = _goal_adjustment_ui_prompt(intake_state)
        if ga is not None:
            return ga

    if phase == PHASE_AWAITING_TRADEOFF_CHOICE:
        tradeoff = _runner_tradeoff_ui_prompt(intake_state)
        if tradeoff is not None:
            return tradeoff

    hr_cal = build_plan_profile_hr_beat_ui_prompt(intake_state)
    if hr_cal is not None:
        return hr_cal

    sched = _schedule_confirmation_ui_prompt(intake_state)
    if sched is not None:
        return sched

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
