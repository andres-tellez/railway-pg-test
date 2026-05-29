"""Coordinator for coach tool plan-generation workflow."""

# pylint: disable=too-many-arguments,too-many-locals,too-many-return-statements,too-many-branches,too-many-statements,broad-exception-caught,missing-function-docstring

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from src.db.dao.plans_dao import get_plan_with_workouts
from src.db.dao.user_profile_dao import get_user_profile
from src.services.training_plan.plan_storage_service import PlanStorageService
from src.services.training_plan.v2.plan_validation_silent_repair import (
    attempt_silent_repair_then_revalidate,
)
from src.services.training_plan.v2.race_distance_factory_v2 import (
    get_race_distance_services,
    normalize_race_distance,
)
from src.smartcoach_mobile_coach import plan_cache, user_context_cache
from src.smartcoach_mobile_coach.plan_creation_ui import (
    PHASE_AWAITING_TRADEOFF_CHOICE,
    PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY,
    PHASE_GENERATED,
    sync_legacy_ux_from_phase,
)
from src.smartcoach_mobile_coach.plan_generation.explanation import (
    build_plan_generation_brief,
    plan_baseline_from_validation,
    plan_overview_from_validation,
)
from src.smartcoach_mobile_coach.plan_generation.readiness import (
    evaluate_generation_readiness,
)
from src.smartcoach_mobile_coach.plan_generation.telemetry import (
    record_plan_generation_tool_event,
)
from src.smartcoach_mobile_coach.plan_intake_flow import (
    PLAN_UX_STAGE_GENERATED,
    plan_creation_split_confirm_enabled,
    summarize_this_week_from_plan_rows,
)

logger = logging.getLogger("smartcoach_mobile_coach")


def _pre_generation_guardrails(
    *,
    confirm: bool,
    current_state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not confirm:
        return {
            "error": "confirmation_required",
            "message": (
                "Ask for explicit confirmation before generating. "
                "Call again with confirm=true once the user says yes."
            ),
            "plan_intake_state": current_state,
            "confirmation_summary": current_state.get("confirmation_summary"),
        }

    ux_gate = (
        current_state.get("ux") if isinstance(current_state.get("ux"), dict) else {}
    )
    if not plan_creation_split_confirm_enabled():
        return None

    if not ux_gate.get("intake_confirmed"):
        return {
            "error": "intake_not_confirmed",
            "tool": "generate_training_plan",
            "message": (
                "Intake recap must be confirmed before generating. "
                "Wait for the user to confirm their race/goal/schedule summary first."
            ),
            "plan_intake_state": current_state,
        }
    if not ux_gate.get("runner_review_delivered"):
        return {
            "error": "runner_review_pending",
            "tool": "generate_training_plan",
            "message": (
                "Runner assessment phase is not complete. "
                "Do not call generate_training_plan until after the review step."
            ),
            "plan_intake_state": current_state,
        }
    if not ux_gate.get("plan_generation_confirmed"):
        return {
            "error": "plan_generation_not_confirmed",
            "tool": "generate_training_plan",
            "message": (
                "The user must explicitly ask to create the plan (e.g. Create my plan) "
                "after the runner assessment-generic yes to the intake recap is not enough."
            ),
            "plan_intake_state": current_state,
        }
    phase_gate = str(ux_gate.get("plan_creation_phase") or "")
    tradeoff_blocked = phase_gate == PHASE_AWAITING_TRADEOFF_CHOICE or (
        not phase_gate and ux_gate.get("runner_tradeoff_pending")
    )
    if tradeoff_blocked:
        return {
            "error": "runner_tradeoff_unresolved",
            "tool": "generate_training_plan",
            "message": (
                "The athlete must pick one of the inline options (or update goal/schedule in chat) "
                "before generating."
            ),
            "plan_intake_state": current_state,
        }
    add_day_blocked = phase_gate == PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY or (
        not phase_gate and ux_gate.get("runner_add_day_pick_pending")
    )
    if add_day_blocked:
        return {
            "error": "runner_add_day_unresolved",
            "tool": "generate_training_plan",
            "message": "The athlete must pick the extra weekday (chips) before generating.",
            "plan_intake_state": current_state,
        }
    pg = ux_gate.get("plan_generation_readiness")
    if isinstance(pg, dict):
        dec = str(pg.get("decision") or "").strip()
        lvl = str(pg.get("readiness_level") or "").strip()
        if dec == "defer" and lvl == "insufficient_data":
            return {
                "error": "runner_review_needs_more_info",
                "tool": "generate_training_plan",
                "message": (
                    "Alignment or goal context is still incomplete - finish open items "
                    "before generating."
                ),
                "plan_intake_state": current_state,
            }
    return None


def generate_training_plan_tool(
    *,
    session: Session,
    internal_user_id: str,
    args: Dict[str, Any],
    current_state: Optional[Dict[str, Any]],
    anchor_local_date: Optional[str],
    coerce_tool_bool: Callable[[Any, bool], bool],
    plan_request_builder: Callable[[Dict[str, Any]], Dict[str, Any]],
    run_plan_fn: Callable[..., tuple[Dict[str, Any], Optional[Dict[str, Any]]]],
    readiness_gate_fn: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(current_state, dict) or not current_state.get("draft"):
        return {
            "error": "no_plan_intake_state",
            "message": "No plan intake state found. Collect plan details first.",
        }

    guard = _pre_generation_guardrails(
        confirm=coerce_tool_bool(args.get("confirm"), False),
        current_state=current_state,
    )
    if guard:
        return guard

    try:
        activity_weeks = int(args.get("activity_weeks", 12))
    except (TypeError, ValueError):
        activity_weeks = 12
    activity_weeks = max(4, min(activity_weeks, 24))

    try:
        plan_request = plan_request_builder(current_state)
    except Exception as exc:
        record_plan_generation_tool_event(
            str(internal_user_id),
            "failure",
            {"stage": "invalid_plan_intake_state", "message": str(exc)[:400]},
        )
        return {
            "error": "invalid_plan_intake_state",
            "message": str(exc),
            "plan_intake_state": current_state,
        }

    blocked, current_state, assessment_payload, readiness_payload = (
        evaluate_generation_readiness(
            session=session,
            internal_user_id=str(internal_user_id),
            plan_request=plan_request,
            current_state=current_state,
            anchor_local_date=anchor_local_date,
            record_event=record_plan_generation_tool_event,
            gate_fn=readiness_gate_fn,
        )
    )
    if blocked is not None:
        return blocked

    try:
        result, gen_context_snapshot = run_plan_fn(
            session=session,
            user_id=str(internal_user_id),
            plan_request=plan_request,
            activity_weeks=activity_weeks,
            mode="rolling",
        )
        if not result.get("valid") or not result.get("validated_plan"):
            plan_blob = result.get("validated_plan") or result.get("draft")
            violations_list = list(result.get("violations") or [])
            if plan_blob and violations_list:
                race_label = normalize_race_distance(
                    plan_request.get("race_distance") or "Marathon"
                )
                race_cfg = get_race_distance_services(race_label)["race_config"]
                profile = get_user_profile(session, str(internal_user_id))
                unit_sys = (
                    (profile.get("unit_system") or "imperial")
                    if profile
                    else "imperial"
                )
                repaired_val = attempt_silent_repair_then_revalidate(
                    plan_blob,
                    violations_list,
                    config=race_cfg,
                    unit_system=str(unit_sys),
                )
                if repaired_val:
                    result.update(
                        {
                            **repaired_val,
                            "draft": repaired_val.get("validated_plan"),
                            "silent_validation_repair_applied": True,
                        }
                    )
    except Exception as exc:
        logger.exception("Plan generation failed user=%s", internal_user_id)
        record_plan_generation_tool_event(
            str(internal_user_id),
            "failure",
            {
                "stage": "plan_generation_exception",
                "exception_type": type(exc).__name__,
            },
        )
        return {
            "error": "plan_generation_failed",
            "message": "Plan generation could not be completed.",
            "failure": {
                "failure_code": "unexpected_error",
                "failure_reason": "An unexpected error occurred while building the plan.",
                "details": {"exception_type": type(exc).__name__},
            },
            "plan_intake_state": current_state,
        }

    if not result.get("valid") or not result.get("validated_plan"):
        violations = [
            v for v in (result.get("violations") or []) if isinstance(v, dict)
        ]
        logger.warning(
            "[generate_training_plan] validation_failed user=%s rules=%s",
            str(internal_user_id)[:8],
            [v.get("rule") for v in violations],
        )
        message = (
            "Your plan couldn't be finalized automatically. "
            "Try a small change to race date or training days, or try again in a moment."
        )
        if violations:
            top = violations[0]
            rule = str(top.get("rule") or "").strip()
            detail = str(top.get("details") or "").strip()
            suggestion = str(top.get("suggestion") or "").strip()
            if rule == "unsafe_long_run_progression" and suggestion:
                message = (
                    "I couldn't finalize the plan because one long-run jump was unsafe. "
                    f"{suggestion}."
                )
            elif detail:
                message = detail
        out = {
            "error": "plan_validation_failed",
            "message": message,
            "plan_intake_state": current_state,
        }
        if violations:
            out["violations"] = violations
        if result.get("generation_failure"):
            out["failure"] = result["generation_failure"]
        record_plan_generation_tool_event(
            str(internal_user_id),
            "failure",
            {
                "stage": "plan_validation_failed",
                "rules": [v.get("rule") for v in violations][:12],
                "trace_id": readiness_payload.get("trace_id"),
            },
        )
        return out

    validation_payload = {
        "valid": True,
        "validated_plan": result["validated_plan"],
        "violations": result.get("violations", []),
    }
    plan_id = PlanStorageService.save_validated_plan(
        session=session,
        user_id=str(internal_user_id),
        validated_plan=validation_payload,
        plan_request=plan_request,
        context_snapshot=gen_context_snapshot,
    )
    session.commit()
    user_context_cache.invalidate_user_context(str(internal_user_id))
    plan_cache.invalidate_user_plan_cache(str(internal_user_id))

    saved = get_plan_with_workouts(session, int(plan_id), str(internal_user_id)) or {}
    week_summary = summarize_this_week_from_plan_rows(saved.get("workouts") or [])
    plan_generation_payload = {
        "plan_id": int(plan_id),
        "plan_name": saved.get("plan_name"),
        "this_week": week_summary,
        "overview": plan_overview_from_validation(result, plan_request, saved),
        "baseline": plan_baseline_from_validation(
            result, activity_weeks=activity_weeks
        ),
        "navigation": {
            "primary_tab": "Plan",
            "hint": "Open the Plan tab to review full workouts and phase-by-phase progression.",
        },
    }
    post_generation_brief = build_plan_generation_brief(
        race_distance=str(saved.get("race_distance") or ""),
        race_date=str(saved.get("race_date") or ""),
        payload=plan_generation_payload,
    )
    next_state = dict(current_state)
    next_state["status"] = "generated"
    next_state["last_generated_plan_id"] = int(plan_id)
    next_ux = dict(next_state.get("ux") or {})
    next_ux["stage"] = PLAN_UX_STAGE_GENERATED
    if plan_creation_split_confirm_enabled():
        next_ux["plan_creation_phase"] = PHASE_GENERATED
        sync_legacy_ux_from_phase(next_ux, PHASE_GENERATED)
    next_state["ux"] = next_ux

    record_plan_generation_tool_event(
        str(internal_user_id),
        "success",
        {
            "plan_id": int(plan_id),
            "trace_id": readiness_payload.get("trace_id"),
            "activity_weeks": activity_weeks,
        },
    )

    training_target_context: Optional[Dict[str, Any]] = None
    try:
        from src.smartcoach_mobile_coach.runner_profile.training_target_context import (
            build_training_target_context,
        )

        training_target_context = build_training_target_context(
            session,
            str(internal_user_id),
            target_time=plan_request.get("target_time"),
            race_distance=plan_request.get("race_distance"),
            primary_goal=plan_request.get("primary_goal"),
        )
    except Exception as exc:
        logger.warning(
            "training_target_context snapshot failed after plan save user=%s: %s",
            str(internal_user_id)[:8],
            exc,
        )

    out: Dict[str, Any] = {
        "ok": True,
        "plan_id": int(plan_id),
        "plan_name": saved.get("plan_name"),
        "race_date": saved.get("race_date"),
        "race_distance": saved.get("race_distance"),
        "this_week": week_summary,
        "post_generation_brief": post_generation_brief,
        "plan_intake_state": next_state,
        "plan_generation": plan_generation_payload,
        "message": "Plan created and activated successfully.",
        "pre_generation_runner_assessment": assessment_payload,
        "plan_generation_readiness": readiness_payload,
    }
    if training_target_context is not None:
        out["training_target_context"] = training_target_context
    return out
