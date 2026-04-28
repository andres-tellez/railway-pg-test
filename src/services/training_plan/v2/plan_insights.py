"""
Plan Insights (Interpreter) — read-only summary from :class:`PlanContext`.

No thresholds, scoring, or recomputation of plan logic.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.services.training_plan.v2.plan_context import PlanContext


def _peak_weeks_before_taper(weeks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    taper_start = next(
        (i for i, w in enumerate(weeks) if w.get("phase") == "Taper"),
        len(weeks),
    )
    return [
        w for i, w in enumerate(weeks) if i < taper_start and w.get("phase") == "Peak"
    ]


def build_plan_insights(context: PlanContext) -> Dict[str, Any]:
    """
    Extracts a structured summary from PlanContext without recomputing logic.
    No thresholds, no scoring, no new business rules.
    """
    plan = context.detailed_plan or {}
    validation = context.validation or {}
    draft = validation.get("draft") or {}
    weeks: List[Dict[str, Any]] = plan.get("weeks") or draft.get("weeks") or []

    long_runs = []
    weekly_miles = []

    for w in weeks:
        lr = w.get("long_run_miles")
        if lr is not None:
            long_runs.append(lr)
        wm = w.get("weekly_mileage")
        if wm is not None:
            weekly_miles.append(wm)

    plan_length = len(weeks)

    peak_long_run = max(long_runs) if long_runs else None
    peak_week_index = (
        (long_runs.index(peak_long_run) + 1) if peak_long_run in long_runs else None
    )

    peak_before_taper = _peak_weeks_before_taper(weeks)
    peak_block_lrs: List[float] = []
    for w in peak_before_taper:
        lr = w.get("long_run_miles")
        if lr is not None:
            peak_block_lrs.append(float(lr))
    peak_phase_evidence: Dict[str, Any] | None = None
    if peak_block_lrs:
        peak_phase_evidence = {
            "max_long_run": max(peak_block_lrs),
            "min_long_run": min(peak_block_lrs),
        }

    first_three = weeks[:3]

    spine_issues = context.spine_quality_issues or []

    return {
        "summary": {
            "plan_length_weeks": plan_length,
            "peak_long_run": peak_long_run,
            "peak_week_index": peak_week_index,
        },
        "long_run": {
            "progression": long_runs,
            "first_three_weeks": [
                {
                    "week_number": w.get("week_number"),
                    "long_run_miles": w.get("long_run_miles"),
                }
                for w in first_three
            ],
        },
        "weekly_load": {
            "weekly_mileage": weekly_miles,
        },
        "validation": {
            "is_valid": validation.get("valid"),
            "issues": validation.get("issues", []),
        },
        "spine_quality": {
            "issues": spine_issues,
        },
        "peak_phase_evidence": peak_phase_evidence,
    }
