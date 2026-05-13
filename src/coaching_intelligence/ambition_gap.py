"""
Ambition-gap evaluator — Phase 3 observational prototype.

Read-only classification of tension between measured weekly volume (baseline proxy)
and stated goal intent. Produces discrete stances and explicit rule attributions.

Does NOT: compute training loads, weekly targets, long-run progression, or call planner code.

Semantic hygiene (v1, intentionally coarse):
- ``stance`` is a legacy snapshot for APIs and display. Prefer ``attributions`` (and
  especially ``STANCE_*`` codes) for branching in readiness and alignment—do not add
  new logic keyed only on ``stance``.
- ``stance`` value ``COHERENT`` is overloaded: finish intent, non-time goal copy, and
  time-goal + established baseline all map here. Disambiguate using ``attributions``,
  not extra stance enums—avoid state-machine expansion in this phase.
- ``goal_demand`` ``GENERAL`` means "stated goal string present but not classified as
  finish or target-time heuristics"—not "moderate ambition" and not ``baseline_band``
  ``MODERATE`` (volume band).
- ``longest_run_miles`` in v1 only adds thin-data attributions when <= 0; it does not
  change bands or stance. Defer richer use until a later phase justifies it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.coaching_intelligence.policy.policy_table import (
    mpw_moderate_max,
    mpw_thin_max,
)


def evaluate_ambition_gap(
    *,
    weekly_mileage: float,
    primary_goal: Optional[str] = None,
    target_time: Optional[str] = None,
    longest_run_miles: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Deterministic ambition-gap evaluation. Same inputs -> same output.

    Args:
        weekly_mileage: Recent average weekly miles (caller-supplied; e.g. from MV).
        primary_goal: Raw goal string from intake.
        target_time: Optional time string when goal is time-oriented.
        longest_run_miles: Optional signal for thin-data notes only in v1.

    Returns:
        Plain dict: stance, baseline_band, goal_demand, attributions, thin_baseline_data.

        ``stance`` / ``goal_demand`` / ``baseline_band`` are small closed sets of strings.
        Multiple situations share ``stance="COHERENT"``; see module docstring.
    """
    attributions: List[str] = []

    thin_baseline_data = weekly_mileage <= 0.0
    if thin_baseline_data:
        attributions.append("RULE_BASELINE_MILEAGE_MISSING_OR_ZERO")
    if longest_run_miles is not None and longest_run_miles <= 0.0:
        attributions.append("RULE_LONGEST_RUN_MISSING_OR_ZERO")

    # 1) Baseline band (ordered thresholds)
    if weekly_mileage < mpw_thin_max:
        baseline_band = "THIN"
        attributions.append("RULE_BASELINE_BAND_THIN")
    elif weekly_mileage < mpw_moderate_max:
        baseline_band = "MODERATE"
        attributions.append("RULE_BASELINE_BAND_MODERATE")
    else:
        baseline_band = "ESTABLISHED"
        attributions.append("RULE_BASELINE_BAND_ESTABLISHED")

    # 2) Goal demand (explicit string rules; no scoring)
    g = (primary_goal or "").strip().lower()
    tt = (target_time or "").strip()

    if g == "just finish" or ("just" in g and "finish" in g):
        goal_demand = "FINISH"
        attributions.append("RULE_GOAL_DEMAND_FINISH")
    elif g == "target time" or ("target" in g and "time" in g):
        goal_demand = "TIME_TARGET"
        attributions.append("RULE_GOAL_DEMAND_TIME_TARGET")
        if tt:
            attributions.append("RULE_GOAL_TIME_STRING_PRESENT")
        else:
            attributions.append("RULE_GOAL_TIME_STRING_ABSENT")
    else:
        if g:
            goal_demand = "GENERAL"
            attributions.append("RULE_GOAL_DEMAND_GENERAL")
        else:
            goal_demand = "UNSPECIFIED"
            attributions.append("RULE_GOAL_DEMAND_UNSPECIFIED")

    # 3) Stance (ordered checks; stances not prescriptions)
    if goal_demand == "UNSPECIFIED":
        stance = "INSUFFICIENT_GOAL_CONTEXT"
        attributions.append("STANCE_INSUFFICIENT_GOAL_CONTEXT")
    elif goal_demand == "FINISH":
        stance = "COHERENT"
        attributions.append("STANCE_COHERENT_FINISH_INTENT")
    elif goal_demand == "GENERAL":
        stance = "COHERENT"
        attributions.append("STANCE_COHERENT_GENERAL_INTENT")
    elif goal_demand == "TIME_TARGET":
        if baseline_band == "THIN":
            stance = "HIGH_TENSION"
            attributions.append("STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE")
        elif baseline_band == "MODERATE":
            stance = "MANAGEABLE_TENSION"
            attributions.append("STANCE_MANAGEABLE_TENSION_TIME_VS_MODERATE_BASELINE")
        else:
            stance = "COHERENT"
            attributions.append("STANCE_COHERENT_TIME_VS_ESTABLISHED_BASELINE")

    return {
        "stance": stance,
        "baseline_band": baseline_band,
        "goal_demand": goal_demand,
        "attributions": attributions,
        "thin_baseline_data": thin_baseline_data,
    }
