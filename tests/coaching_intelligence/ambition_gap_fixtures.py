"""
Synthetic ambition_gap ``attributions`` for tests.

Keeps lists aligned with ``evaluate_ambition_gap`` ordering and codes so
readiness / alignment tests match production payloads (see ``docs/plan_cleanup_tracker.md``).
"""

from __future__ import annotations

from typing import List


def synthetic_ambition_attributions(
    *,
    baseline_band: str,
    goal_demand: str,
    thin_baseline_data: bool = False,
    longest_run_miles: float = 8.0,
    target_time_present: bool = True,
) -> List[str]:
    attributions: List[str] = []
    if thin_baseline_data:
        attributions.append("RULE_BASELINE_MILEAGE_MISSING_OR_ZERO")
    if longest_run_miles <= 0.0:
        attributions.append("RULE_LONGEST_RUN_MISSING_OR_ZERO")
    band = baseline_band.strip().upper()
    if band == "THIN":
        attributions.append("RULE_BASELINE_BAND_THIN")
    elif band == "MODERATE":
        attributions.append("RULE_BASELINE_BAND_MODERATE")
    else:
        attributions.append("RULE_BASELINE_BAND_ESTABLISHED")
    gd = goal_demand.strip().upper()
    if gd == "FINISH":
        attributions.append("RULE_GOAL_DEMAND_FINISH")
        attributions.append("STANCE_COHERENT_FINISH_INTENT")
    elif gd == "TIME_TARGET":
        attributions.append("RULE_GOAL_DEMAND_TIME_TARGET")
        if target_time_present:
            attributions.append("RULE_GOAL_TIME_STRING_PRESENT")
        else:
            attributions.append("RULE_GOAL_TIME_STRING_ABSENT")
        if band == "THIN":
            attributions.append("STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE")
        elif band == "MODERATE":
            attributions.append("STANCE_MANAGEABLE_TENSION_TIME_VS_MODERATE_BASELINE")
        else:
            attributions.append("STANCE_COHERENT_TIME_VS_ESTABLISHED_BASELINE")
    elif gd == "GENERAL":
        attributions.append("RULE_GOAL_DEMAND_GENERAL")
        attributions.append("STANCE_COHERENT_GENERAL_INTENT")
    elif gd == "UNSPECIFIED":
        attributions.append("RULE_GOAL_DEMAND_UNSPECIFIED")
        attributions.append("STANCE_INSUFFICIENT_GOAL_CONTEXT")
    else:
        raise ValueError(
            f"unsupported goal_demand for synthetic attributions: {goal_demand!r}"
        )
    return attributions
