"""
Plan-creation profile HR beat (birth year → optional max HR).

Not the same as global ``HRMaxResolutionService.get_hr_calibration_status`` (activity-based
max HR). This module only drives optional Coach UI after ``ready_to_generate``.

Persists birth year / max HR to ``user_profile`` only. Does not gate plan generation.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from src.db.dao.user_profile_dao import get_user_profile, save_user_profile
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.utils.hr_zone_constants import manual_max_hr_bpm_bounds

PLAN_PROFILE_HR_STEP_BIRTH_YEAR = "birth_year"
PLAN_PROFILE_HR_STEP_MAX_HR = "max_hr"

PLAN_PROFILE_HR_BIRTH_YEAR_PROMPT = (
    "What year were you born? This helps estimate heart-rate zones "
    "if you don't enter a max heart rate."
)
PLAN_PROFILE_HR_MAX_HR_PROMPT = (
    "What is your max heart rate (bpm)? Only enter it if you know it — don't guess."
)

# Back-compat aliases for imports/tests
HR_CALIBRATION_STEP_BIRTH_YEAR = PLAN_PROFILE_HR_STEP_BIRTH_YEAR
HR_CALIBRATION_STEP_MAX_HR = PLAN_PROFILE_HR_STEP_MAX_HR


def minimal_coach_bootstrap_profile(user_id: str) -> Dict[str, Any]:
    """Placeholder body stats so INSERT satisfies NOT NULL columns until onboarding fills real values."""
    return {
        "user_id": str(user_id),
        "age_group": "30-39",
        "unit_system": "imperial",
        "height_feet": 5,
        "height_inches": 10,
        "weight": 165.0,
    }


def ensure_user_profile_row(session: Any, user_id: str) -> Dict[str, Any]:
    """Create a minimal profile row so Coach can save birth year / max HR without onboarding."""
    existing = get_user_profile(session, str(user_id))
    if existing:
        return dict(existing)
    save_user_profile(session, minimal_coach_bootstrap_profile(str(user_id)))
    return dict(
        get_user_profile(session, str(user_id))
        or minimal_coach_bootstrap_profile(str(user_id))
    )


def sync_plan_profile_hr_beat_ux(
    session: Any,
    user_id: str,
    intake_state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Derive ``ux.hr_calibration_*`` from ``user_profile`` + ephemeral skip flags.

    Does not change ``ready_to_generate`` or ``missing_required``.
    Call after ``update_plan_intake`` merges, or at the start of ``compute_plan_creation_ui``
    when ``session`` and ``user_id`` are available.
    """
    state = dict(intake_state)
    ux = dict(state.get("ux") or {})

    if not state.get("ready_to_generate"):
        state["ux"] = ux
        return state

    profile = get_user_profile(session, str(user_id)) or {}
    has_birth = profile.get("birth_year") is not None
    has_manual = profile.get("max_hr_manual") is not None
    skipped_max = bool(ux.get("hr_calibration_max_hr_skipped"))
    skipped_birth = bool(ux.get("hr_calibration_birth_year_skipped"))

    if has_manual or skipped_max:
        ux["hr_calibration_intake_done"] = True
        ux.pop("hr_calibration_step", None)
    elif not has_birth and not skipped_birth:
        ux["hr_calibration_intake_done"] = False
        ux["hr_calibration_step"] = PLAN_PROFILE_HR_STEP_BIRTH_YEAR
    else:
        ux["hr_calibration_intake_done"] = False
        ux["hr_calibration_step"] = PLAN_PROFILE_HR_STEP_MAX_HR

    state["ux"] = ux
    return state


sync_hr_calibration_ux = sync_plan_profile_hr_beat_ux


def plan_profile_hr_beat_ui_active(intake_state: Dict[str, Any]) -> bool:
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    if ux.get("hr_calibration_intake_done"):
        return False
    step = ux.get("hr_calibration_step")
    return step in (PLAN_PROFILE_HR_STEP_BIRTH_YEAR, PLAN_PROFILE_HR_STEP_MAX_HR)


hr_calibration_ui_prompt_active = plan_profile_hr_beat_ui_active


def build_plan_profile_hr_beat_ui_prompt(
    intake_state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Inline controls for optional birth year then optional max HR."""
    if not plan_profile_hr_beat_ui_active(intake_state):
        return None

    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    step = ux.get("hr_calibration_step")
    now_y = date.today().year
    min_y = 1920
    max_y = now_y - 13

    if step == PLAN_PROFILE_HR_STEP_BIRTH_YEAR:
        return {
            "version": 1,
            "field_key": "user_profile.birth_year",
            "control_type": "year_select",
            "selection_mode": "single",
            "required": False,
            "prompt": PLAN_PROFILE_HR_BIRTH_YEAR_PROMPT,
            "options": [
                {
                    "id": "birth_year_skip",
                    "label": "Skip",
                    "user_message": "I'd rather not share my birth year.",
                    "updates": {"hr_calibration_birth_year_skipped": True},
                },
            ],
            "min_year": min_y,
            "max_year": max_y,
        }

    if step == PLAN_PROFILE_HR_STEP_MAX_HR:
        return {
            "version": 1,
            "field_key": "user_profile.max_hr_manual",
            "control_type": "optional_bpm",
            "selection_mode": "single",
            "required": False,
            "prompt": PLAN_PROFILE_HR_MAX_HR_PROMPT,
            "options": [
                {
                    "id": "max_hr_skip",
                    "label": "Skip — I don't know",
                    "user_message": "I don't know my max heart rate.",
                    "updates": {"hr_calibration_max_hr_skipped": True},
                },
            ],
        }

    return None


build_hr_calibration_ui_prompt = build_plan_profile_hr_beat_ui_prompt


def merge_max_hr_manual_into_profile(
    session: Any,
    user_id: str,
    max_hr_manual: int,
) -> Optional[str]:
    """
    Persist manual max HR. Returns error message string on failure, else None.
    """
    profile = ensure_user_profile_row(session, str(user_id))
    lo, hi = manual_max_hr_bpm_bounds(profile.get("birth_year"))
    if max_hr_manual < lo or max_hr_manual > hi:
        if profile.get("birth_year") is None:
            return f"Max HR must be between {lo} and {hi} bpm."
        return f"Max HR must be between {lo} and {hi} bpm for your age."

    merged = dict(profile)
    merged["user_id"] = str(user_id)
    merged["max_hr_manual"] = int(max_hr_manual)
    merged["max_hr_active"] = "manual"
    merged.pop("max_hr", None)
    save_user_profile(session, merged)

    old_effective = HRMaxResolutionService.get_effective_max_hr(profile)
    new_effective = HRMaxResolutionService.get_effective_max_hr(merged)
    if new_effective != old_effective:
        try:
            from src.services.training_plan.recalculate_hr_zones_service import (
                recalculate_hr_zones_for_user,
            )

            recalculate_hr_zones_for_user(session, str(user_id))
        except Exception:
            pass
    return None


def merge_ui_prompt_into_assistant_payload(
    assistant_payload: Dict[str, Any],
    ui: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Attach ``ui_prompt`` and append its question into assistant ``content`` when present."""
    out = dict(assistant_payload)
    if not isinstance(ui, dict):
        return out
    data = dict(out.get("data") or {})
    data["ui_prompt"] = ui
    out["data"] = data
    prompt_text = str(ui.get("prompt") or "").strip()
    if prompt_text:
        existing = str(out.get("content") or "").strip()
        out["content"] = f"{existing}\n\n{prompt_text}" if existing else prompt_text
    return out


def attach_plan_intake_ui_after_profile_patch(
    session: Any,
    internal_user_id: str,
    prior_messages: list,
    assistant_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach synced ``plan_intake_state`` + next ``ui_prompt`` after a profile patch turn."""
    from src.smartcoach_mobile_coach.plan_creation_ui import compute_plan_creation_ui
    from src.smartcoach_mobile_coach.thread_derived_context import (
        derive_thread_coach_context,
    )

    raw_history = [{"role": m.role, "content": m.content or ""} for m in prior_messages]
    thread_ctx = derive_thread_coach_context(raw_history)
    pis = thread_ctx.latest_plan_intake_state
    if not isinstance(pis, dict) or not pis.get("ready_to_generate"):
        return assistant_payload

    pis = sync_plan_profile_hr_beat_ux(session, str(internal_user_id), pis)
    out = dict(assistant_payload)
    data = dict(out.get("data") or {})
    data["plan_intake_state"] = pis
    ui = compute_plan_creation_ui(pis)
    out["data"] = data
    return merge_ui_prompt_into_assistant_payload(
        out, ui if isinstance(ui, dict) else None
    )
