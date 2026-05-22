"""Shape the final mobile-facing payload for coach response turns."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Tuple

from src.smartcoach_mobile_coach.coach_response.context import CoachRunContext
from src.smartcoach_mobile_coach.coach_response.prompt import (
    COACH_RESPONSE_PROMPT_VERSION,
)
from src.smartcoach_mobile_coach.run_summary_sections import (
    enrich_run_summary_payload_with_sections,
)

RunSummaryLayout = Literal["recap", "inline"]
RUN_SUMMARY_LAYOUT_RECAP: RunSummaryLayout = "recap"
RUN_SUMMARY_LAYOUT_INLINE: RunSummaryLayout = "inline"


def build_payload_data(ctx: CoachRunContext) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "facts": ctx.facts,
    }
    if ctx.activity_id and int(ctx.activity_id) > 0:
        data["activity_id"] = int(ctx.activity_id)
    if ctx.training_kpis is not None:
        data["training_kpis"] = ctx.training_kpis
    if ctx.zone_bounds is not None:
        data["zone_bounds"] = ctx.zone_bounds
    if ctx.hr_drift_band_zones is not None:
        data["hr_drift_band_zones"] = ctx.hr_drift_band_zones
    if ctx.is_easy_run is not None:
        data["is_easy_run"] = ctx.is_easy_run
    if ctx.hr_profile is not None:
        data["user_hr_profile"] = ctx.hr_profile
    if isinstance(ctx.splits, dict) and ctx.splits.get("splits"):
        data["splits"] = ctx.splits
    return data


def build_coach_response_envelope(
    *,
    ctx: CoachRunContext,
    content: str,
    run_summary_layout: RunSummaryLayout = RUN_SUMMARY_LAYOUT_RECAP,
) -> Tuple[Dict[str, Any], bool]:
    layout = (
        run_summary_layout
        if run_summary_layout in (RUN_SUMMARY_LAYOUT_RECAP, RUN_SUMMARY_LAYOUT_INLINE)
        else RUN_SUMMARY_LAYOUT_RECAP
    )
    structured: Dict[str, Any] = {
        "type": "run_summary",
        "content": (content or "").strip(),
        "data": build_payload_data(ctx),
    }
    if layout != RUN_SUMMARY_LAYOUT_RECAP:
        structured["run_summary_layout"] = layout
    structured, sections_attached = enrich_run_summary_payload_with_sections(structured)
    return structured, sections_attached


def build_coach_response_meta(
    *,
    ctx: CoachRunContext,
    usage: Dict[str, int],
    cost: float,
    model: str,
    timings_ms: Dict[str, Any],
    dialogue: Dict[str, Any],
    sections_attached: bool,
    classifier_summary: Dict[str, Any],
    coach_context_trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "usage": usage,
        "cost": cost,
        "loops": 1,
        "max_loops": 1,
        "model": model,
        "coach_response_v1": True,
        "coach_response_path": ctx.resolved_via,
        "coach_response_scope": ctx.scope,
        "coach_response_activity_id": ctx.activity_id,
        "coach_response_classifier": classifier_summary,
        "timings_ms": timings_ms,
        "dialogue": dialogue,
        "rubric_version": COACH_RESPONSE_PROMPT_VERSION,
        "evidence_pack_trace": ctx.evidence_pack_trace,
    }
    if sections_attached:
        meta["run_summary_sections"] = True
    if isinstance(coach_context_trace, dict):
        meta["coach_context_trace"] = coach_context_trace
    return meta
