"""
Passive container for V2 plan generation pipeline artifacts.

Holds references to intermediate results only; no generation logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.services.training_plan.decision_trace import DecisionReason
    from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneComputation


@dataclass
class PlanContext:
    """Mirrors orchestrator stages; fields are assigned as the pipeline runs."""

    fitness: Optional[Dict[str, Any]] = None
    plan_length_weeks: Optional[int] = None
    scenario_adjustments: Optional[Dict[str, Any]] = None
    pass1_output: Optional[Dict[str, Any]] = None
    spine_quality_issues: Optional[List[dict]] = None
    spine_weeks: Optional[List[Dict[str, Any]]] = None
    weekly_totals: Optional[List[Dict[str, Any]]] = None
    workout_distribution: Optional[Dict[str, Any]] = None
    detailed_plan: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    decision_trace: Optional[List[Dict[str, Any]]] = None
    pace_zones: Optional[PaceZoneComputation] = None
    training_days_reason: Optional[DecisionReason] = None
    long_run_day_reason: Optional[DecisionReason] = None
    enable_debug_trace: bool = False
    stage_trace: List[Dict[str, Any]] = field(default_factory=list)
