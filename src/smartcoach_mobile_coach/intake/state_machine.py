"""Recompute derived intake state (missing, ready flags, UX) after merges (Phase 7.1)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.smartcoach_mobile_coach.intake import soft_reset as sr


def finalize_plan_intake_state(
    *,
    draft: Dict[str, Any],
    ux: Dict[str, Any],
    errors: List[str],
    alignment: Dict[str, Any],
    alignment_answers: Dict[str, Any],
    up: Dict[str, Any],
    prior_digest: tuple,
    prior_ux_snapshot: Dict[str, Any],
    prior_training_days_for_expansion: Optional[List[str]],
    prior_expansion_pending: bool,
    had_prior_draft: bool,
    prior_ready_to_generate: bool,
    source_user_message: Optional[str],
) -> Dict[str, Any]:
    from src.smartcoach_mobile_coach import plan_intake_flow as pif

    sr.maybe_reset_split_confirm_on_material_draft_change(
        draft=draft,
        prior_digest=prior_digest,
        up=up,
        prior_ux_snapshot=prior_ux_snapshot,
        ux=ux,
    )

    if ux.get("training_days_expansion_pending"):
        explicit_td = isinstance(up, dict) and "training_days" in up
        cur_td = draft.get("training_days")
        td_changed = False
        if isinstance(cur_td, list):
            if isinstance(prior_training_days_for_expansion, list):
                td_changed = cur_td != prior_training_days_for_expansion
            else:
                td_changed = True
        if explicit_td or td_changed:
            ux.pop("training_days_expansion_pending", None)
            ux.pop("runner_add_day_pick_pending", None)
            ux.pop("expansion_base_training_days", None)

    expansion_cleared_this_turn = prior_expansion_pending and not ux.get(
        "training_days_expansion_pending"
    )
    if expansion_cleared_this_turn:
        ux["schedule_confirm_before_posture"] = True

    missing = pif._missing_required_fields(draft)
    if ux.get("training_days_expansion_pending"):
        if "training_days" not in missing:
            missing = ["training_days"] + [m for m in missing if m != "training_days"]
    ready_to_generate = len(missing) == 0 and len(errors) == 0
    status = "ready_to_confirm" if not missing else "collecting"
    ux["stage"] = pif._plan_ux_stage_for_state(
        draft,
        missing,
        ready_to_generate=ready_to_generate,
        had_prior_draft=had_prior_draft,
        prior_ready_to_generate=prior_ready_to_generate,
    )
    state: Dict[str, Any] = {
        "version": 1,
        "status": status,
        "draft": draft,
        "ux": ux,
        "missing_required": missing,
        "missing_required_labels": [pif._human_missing_label(m) for m in missing],
        "ready_to_generate": ready_to_generate,
        "errors": errors,
        "confirmation_summary": pif._confirmation_summary(draft),
    }
    merged_al: Optional[Dict[str, Any]] = None
    if alignment_answers:
        merged_al = {**alignment, "answers": alignment_answers}
    elif alignment:
        merged_al = dict(alignment)
    if merged_al is not None:
        state["alignment"] = pif._recompute_alignment_branch(merged_al, draft)
    if pif._intake_alignment_feature_enabled():
        al_out = state.get("alignment")
        if isinstance(al_out, dict):
            ast = al_out.get("state")
            if (
                isinstance(ast, dict)
                and ast.get("pause_required")
                and not ast.get("generation_ready")
            ):
                state["ready_to_generate"] = False
                state["status"] = "collecting"
                state["ux"]["stage"] = pif._plan_ux_stage_for_state(
                    draft,
                    state["missing_required"],
                    ready_to_generate=False,
                    had_prior_draft=had_prior_draft,
                    prior_ready_to_generate=prior_ready_to_generate,
                )
    if pif.plan_creation_split_confirm_enabled():
        u_final = dict(state.get("ux") or {})
        if state.get("ready_to_generate"):
            msg_end = (source_user_message or "").strip()
            chip_ok = isinstance(up, dict) and pif._truthy(
                up.get("plan_generation_confirmed")
            )
            plan_requested = pif.user_requests_plan_generation(msg_end) or chip_ok
            if pif.user_confirms_plan_intake(msg_end) or plan_requested:
                u_final["intake_confirmed"] = True
            if plan_requested:
                u_final["plan_generation_confirmed"] = True
        state["ux"] = u_final
    pif._sync_plan_creation_phase_and_legacy_flags(state)
    return state
