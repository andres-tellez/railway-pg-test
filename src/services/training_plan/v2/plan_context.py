"""
Passive container for V2 plan generation pipeline artifacts.

Holds references to intermediate results only; no generation logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.services.training_plan.decision_trace import DecisionReason
    from src.services.training_plan.pace import PaceSeed


@dataclass
class PlanContext:
    """Mirrors orchestrator stages; fields are assigned as the pipeline runs."""

    fitness: Optional[Dict[str, Any]] = None
    plan_length_weeks: Optional[int] = None
    scenario_adjustments: Optional[Dict[str, Any]] = None
    pass1_output: Optional[Dict[str, Any]] = None
    spine_weeks: Optional[List[Dict[str, Any]]] = None
    weekly_totals: Optional[List[Dict[str, Any]]] = None
    workout_distribution: Optional[Dict[str, Any]] = None
    detailed_plan: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    decision_trace: Optional[List[Dict[str, Any]]] = None
    pace_seed: Optional[PaceSeed] = None
    training_days_reason: Optional[DecisionReason] = None
    long_run_day_reason: Optional[DecisionReason] = None
