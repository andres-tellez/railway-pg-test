"""
Shape the final mobile-facing payload for a Run Review turn.

We preserve ``type: "run_summary"`` so thread-derived ``activity_id`` and the
RunSummaryCard contract stay stable. ``run_summary_layout`` selects client chrome:

- Omit or ``recap``: metrics card + insight (default).
- ``inline``: Markdown-only body (e.g. lab ``splits_only``).
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Tuple

from src.smartcoach_mobile_coach.run_review.context import RunReviewContext
from src.smartcoach_mobile_coach.run_review.prompt import RUN_REVIEW_RUBRIC_VERSION
from src.smartcoach_mobile_coach.run_summary_sections import (
    enrich_run_summary_payload_with_sections,
)

# Client presentation for ``type: run_summary`` — omit on wire when ``recap`` (default).
RunSummaryLayout = Literal["recap", "inline"]
RUN_SUMMARY_LAYOUT_RECAP: RunSummaryLayout = "recap"
RUN_SUMMARY_LAYOUT_INLINE: RunSummaryLayout = "inline"


def build_payload_data(ctx: RunReviewContext) -> Dict[str, Any]:
    """
    Reconstruct the ``data`` portion of the run_summary envelope from the
    context object. We keep the same top-level keys the legacy path
    produces (``facts``, ``training_kpis``, etc.) so the mobile parser
    stays untouched.
    """
    data: Dict[str, Any] = {
        "facts": ctx.facts,
    }
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


def build_run_review_envelope(
    *,
    ctx: RunReviewContext,
    content: str,
    run_summary_layout: RunSummaryLayout = RUN_SUMMARY_LAYOUT_RECAP,
) -> Tuple[Dict[str, Any], bool]:
    """Return ``(structured_payload, sections_attached_bool)``.

    ``run_summary_layout`` controls mobile chrome without changing ``type``:

    - ``recap`` (default): metrics card + insight bubble (historical behavior).
    - ``inline``: prose/splits Markdown only — used for lab ``splits_only`` turns.

    ``type`` stays ``run_summary`` so thread-derived ``activity_id`` parsing is unchanged.
    """
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


def build_run_review_meta(
    *,
    ctx: RunReviewContext,
    usage: Dict[str, int],
    cost: float,
    model: str,
    timings_ms: Dict[str, Any],
    dialogue: Dict[str, Any],
    sections_attached: bool,
    classifier_summary: Dict[str, Any],
    coach_context_trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compose the meta dict mirroring the legacy fastpath shape."""
    meta: Dict[str, Any] = {
        "usage": usage,
        "cost": cost,
        "loops": 1,
        "max_loops": 1,
        "model": model,
        "run_review_v2": True,
        "run_review_v2_path": ctx.resolved_via,
        "run_review_v2_scope": ctx.scope,
        "run_review_v2_activity_id": ctx.activity_id,
        "run_review_v2_classifier": classifier_summary,
        "timings_ms": timings_ms,
        "dialogue": dialogue,
        "rubric_version": RUN_REVIEW_RUBRIC_VERSION,
        "evidence_pack_trace": ctx.evidence_pack_trace,
    }
    if sections_attached:
        meta["run_summary_sections"] = True
    if isinstance(coach_context_trace, dict):
        meta["coach_context_trace"] = coach_context_trace
    return meta


def maybe_inject_activity_hint_for_thread(
    ctx: RunReviewContext, prior_thread_hint: Optional[int]
) -> int:
    """Provide the next turn's thread-context activity hint.

    The orchestrator stores a thread activity id so a follow-up like
    "what about my splits?" can resolve without re-prompting. We return
    the V2 activity id when present, falling back to whatever the
    orchestrator already had.
    """
    if ctx.activity_id and ctx.activity_id > 0:
        return int(ctx.activity_id)
    return int(prior_thread_hint or 0)
