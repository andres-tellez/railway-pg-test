"""Split-confirm UX reset helpers (Phase 7.1)."""

from __future__ import annotations

import os
from typing import Any, Dict


def _plan_creation_split_confirm_enabled() -> bool:
    raw = (
        (os.getenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1") or "1").strip().lower()
    )
    return raw not in ("0", "false", "no", "off")


def clear_plan_confirmation_ux(ux: Dict[str, Any]) -> None:
    ux.pop("intake_confirmed", None)
    ux.pop("runner_review_delivered", None)
    ux.pop("plan_generation_confirmed", None)
    ux.pop("runner_tradeoff_pending", None)
    ux.pop("runner_tradeoff_resolved", None)
    ux.pop("runner_review_assessment_status", None)
    ux.pop("plan_generation_readiness", None)
    ux.pop("runner_tradeoff_edit_focus", None)
    ux.pop("runner_add_day_pick_pending", None)
    ux.pop("expansion_base_training_days", None)
    ux.pop("plan_creation_phase", None)


def soft_reset_runner_review_after_goal_edit(ux: Dict[str, Any]) -> None:
    """Keep intake confirmation; clear stale runner review consent after a material goal edit."""
    ux.pop("plan_generation_confirmed", None)
    ux.pop("runner_review_delivered", None)
    ux.pop("runner_tradeoff_resolved", None)
    ux.pop("runner_tradeoff_edit_focus", None)
    ux.pop("runner_goal_edit_pending", None)
    ux.pop("plan_generation_readiness", None)
    ux.pop("plan_creation_phase", None)


def maybe_reset_split_confirm_on_material_draft_change(
    *,
    draft: Dict[str, Any],
    prior_digest: tuple,
    up: Dict[str, Any],
    prior_ux_snapshot: Dict[str, Any],
    ux: Dict[str, Any],
) -> None:
    """Clear split-confirm UX when material draft fields change (with tradeoff/goal-edit nuance)."""
    if not _plan_creation_split_confirm_enabled():
        return
    from src.smartcoach_mobile_coach import plan_intake_flow as pif

    if pif._material_draft_digest(draft) != prior_digest:
        tradeoff_expand = (
            isinstance(up, dict)
            and str(up.get("runner_tradeoff_choice") or "").strip().lower()
            == "expand_running_days"
        )
        goal_ux_touch = isinstance(up, dict) and (
            "target_time" in up or "primary_goal" in up
        )
        from_goal_edit_flow = bool(
            prior_ux_snapshot.get("runner_goal_edit_pending")
            or prior_ux_snapshot.get("runner_tradeoff_edit_focus") == "goal"
        )
        if not tradeoff_expand:
            if goal_ux_touch and from_goal_edit_flow:
                soft_reset_runner_review_after_goal_edit(ux)
            else:
                clear_plan_confirmation_ux(ux)
