"""
Purpose:
- Define the CoachSnapshot schema v1 and slice dataclasses.

Responsibilities:
- Provide stable typed structures for athlete/plan/trends/memory/working slices.
- Provide deterministic `to_dict()` serialization for prompt + telemetry layers.

Non-goals:
- No database access.
- No prompt rendering or business logic.

Guardrails:
- Allowed imports/calls: stdlib dataclasses/typing only.
- Must not import orchestrator, tools, or service modules.
- Must not compute or mutate source-of-truth data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AthleteSlice:
    display_name: Optional[str]
    unit_system: str
    baseline_status: Optional[str]
    hr_calibration_status: str
    zones_compact: Optional[Dict[str, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanSlice:
    has_active_plan: bool
    race: Optional[Dict[str, Any]] = None
    phase: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrendsSlice:
    mileage_4w: List[int]
    mileage_delta_last_vs_avg: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MemorySlice:
    plan_memories: List[Dict[str, str]] = field(default_factory=list)
    session_summary_excerpt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkingContextSlice:
    last_structured_run_activity_id: Optional[int]
    prior_run_summary_in_thread: bool
    plan_creation_clarification_pending: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CoachSnapshot:
    schema_version: int
    today: str
    tz: Optional[str]
    athlete: Optional[AthleteSlice]
    plan: Optional[PlanSlice]
    trends: Optional[TrendsSlice]
    memory: Optional[MemorySlice]
    working: Optional[WorkingContextSlice]
    omitted_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "today": self.today,
            "tz": self.tz,
            "athlete": self.athlete.to_dict() if self.athlete else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "trends": self.trends.to_dict() if self.trends else None,
            "memory": self.memory.to_dict() if self.memory else None,
            "working": self.working.to_dict() if self.working else None,
            "omitted_fields": list(self.omitted_fields or []),
        }
        return out


@dataclass
class SnapshotBuildResult:
    snapshot: CoachSnapshot
    trace: Dict[str, Any]
