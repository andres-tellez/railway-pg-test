"""Coach response run context data contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_LLM_OMIT_FACT_KEYS = frozenset(
    {
        "distance_display",
        "moving_time_display",
        "duration_display",
        "avg_pace_display",
        "avg_heart_rate_display",
        "max_heart_rate_display",
    }
)
_LLM_OMIT_TRAINING_KPI_KEYS = frozenset(
    {
        "hr_drift_pct",
        "hr_drift_band",
        "hr_drift_summary_display",
        "easy_pct",
        "z2_band_pct",
        "easy_pct_display",
        "z2_band_pct_display",
        "early_hr",
        "late_hr",
        "peak_split_hr",
    }
)


@dataclass
class WorkoutIntent:
    planned_type: Optional[str] = None
    planned_miles: Optional[float] = None
    plan_status: Optional[str] = None
    violated_rest_day: Optional[bool] = None

    @property
    def is_quality_session(self) -> bool:
        session_type = (self.planned_type or "").strip().lower()
        return session_type in {
            "tempo",
            "threshold",
            "interval",
            "intervals",
            "speed",
            "progression",
            "race",
        }

    @property
    def is_easy_or_long(self) -> bool:
        session_type = (self.planned_type or "").strip().lower()
        return session_type in {"easy", "recovery", "long", "long_run"}

    def to_prompt_dict(self) -> Dict[str, Any]:
        return {
            "planned_type": self.planned_type,
            "planned_miles": self.planned_miles,
            "plan_status": self.plan_status,
            "violated_rest_day": self.violated_rest_day,
            "is_quality_session": self.is_quality_session,
            "is_easy_or_long": self.is_easy_or_long,
        }


@dataclass
class CoachRunContext:
    activity_id: int
    anchor_local_date: str
    facts: Dict[str, Any] = field(default_factory=dict)
    training_kpis: Optional[Dict[str, Any]] = None
    zone_bounds: Optional[Dict[str, Any]] = None
    hr_drift_band_zones: Optional[Any] = None
    is_easy_run: Optional[bool] = None
    workout_intent: WorkoutIntent = field(default_factory=WorkoutIntent)
    splits: Optional[Dict[str, Any]] = None
    splits_truncated: bool = False
    splits_count: int = 0
    hr_profile: Optional[Dict[str, Any]] = None
    evidence_pack: Optional[Dict[str, Any]] = None
    evidence_pack_trace: Optional[Dict[str, Any]] = None
    week_volume: Optional[Dict[str, Any]] = None
    comparison_sessions: Optional[List[Dict[str, Any]]] = None
    resolved_via: str = ""
    scope: str = "single_run"

    def to_compact_dict(self, *, for_llm: bool = False) -> Dict[str, Any]:
        facts_for_llm = self.facts
        if for_llm and isinstance(self.facts, dict):
            facts_for_llm = {
                key: value
                for key, value in self.facts.items()
                if key not in _LLM_OMIT_FACT_KEYS
            }
        out: Dict[str, Any] = {
            "activity_id": self.activity_id,
            "anchor_local_date": self.anchor_local_date,
            "scope": self.scope,
            "facts": facts_for_llm,
            "workout_intent": self.workout_intent.to_prompt_dict(),
        }
        if self.training_kpis is not None:
            if for_llm:
                slim = {
                    key: value
                    for key, value in self.training_kpis.items()
                    if key not in _LLM_OMIT_TRAINING_KPI_KEYS
                }
                if slim:
                    out["training_kpis"] = slim
            else:
                out["training_kpis"] = self.training_kpis
        if self.zone_bounds is not None:
            out["zone_bounds"] = self.zone_bounds
        if self.hr_drift_band_zones is not None:
            out["hr_drift_band_zones"] = self.hr_drift_band_zones
        if self.is_easy_run is not None:
            out["is_easy_run"] = self.is_easy_run
        if self.hr_profile is not None:
            out["hr_profile"] = self.hr_profile
        if self.evidence_pack is not None:
            out["evidence_pack"] = self.evidence_pack
        if self.splits is not None:
            out["splits"] = self.splits
            out["splits_truncated"] = self.splits_truncated
            out["splits_count"] = self.splits_count
        if self.week_volume is not None:
            out["week_volume"] = self.week_volume
        if self.comparison_sessions:
            out["comparison_sessions"] = self.comparison_sessions
        return out


def stub_context_for_test(  # pragma: no cover
    *,
    activity_id: int,
    anchor_local_date: str,
    facts: Dict[str, Any],
    training_kpis: Optional[Dict[str, Any]] = None,
    zone_bounds: Optional[Dict[str, Any]] = None,
    splits_payload: Optional[Dict[str, Any]] = None,
    scope: str = "single_run",
    is_easy_run: Optional[bool] = None,
    hr_profile: Optional[Dict[str, Any]] = None,
    evidence_pack: Optional[Dict[str, Any]] = None,
    evidence_pack_trace: Optional[Dict[str, Any]] = None,
) -> CoachRunContext:
    workout_intent = WorkoutIntent()
    rows: List[Dict[str, Any]] = (
        (splits_payload or {}).get("splits") if splits_payload else []
    ) or []
    return CoachRunContext(
        activity_id=activity_id,
        anchor_local_date=anchor_local_date,
        facts=facts,
        training_kpis=training_kpis,
        zone_bounds=zone_bounds,
        is_easy_run=is_easy_run,
        workout_intent=workout_intent,
        splits=splits_payload,
        splits_truncated=bool((splits_payload or {}).get("splits_truncated", False)),
        splits_count=len(rows),
        hr_profile=hr_profile,
        evidence_pack=evidence_pack,
        evidence_pack_trace=evidence_pack_trace,
        resolved_via="test_stub",
        scope=scope,
    )
