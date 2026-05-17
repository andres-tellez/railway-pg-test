"""
Run Review V2 context object.

This is the data contract between :mod:`.context_builder` (gather phase)
and :mod:`.prompt` (assemble phase). We keep it explicit so it shows up
clearly in tests and so we never accidentally inflate the payload with
arbitrary tool output.

Design notes:

- ``facts``, ``training_kpis``, ``zone_bounds``, ``splits`` mirror the
  shapes returned by the existing agent tools (no remapping). For LLM
  prompts, ``to_compact_dict(for_llm=True)`` drops only HR drift chip
  keys from ``training_kpis`` (see ``_LLM_OMIT_TRAINING_KPI_KEYS``).
- ``workout_intent`` is a *derived* hint, **not** a verdict. It's a
  lightweight read from ``facts.execution_summary.planned.type`` so the
  model can frame its read correctly (tempo vs easy vs long etc.). The
  model is still responsible for the actual coaching judgment.
- ``hr_profile`` carries the saved Z1–Z5 zones when available. If
  Strava/HR data are missing, the prompt instructs the LLM to skip
  zone-based language.

Every field is optional except ``activity_id`` and ``facts``. The builder
raises :class:`RunReviewFallback` if it can't satisfy that minimum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Shallow-removed from ``training_kpis`` when serializing for the LLM so the
# coach does not repeat RunSummary drift % / band chip content; mobile payload
# still receives the full dict via :func:`run_review.payload.build_payload_data`.
_LLM_OMIT_TRAINING_KPI_KEYS = frozenset(
    {"hr_drift_pct", "hr_drift_band", "hr_drift_summary_display"}
)

_KNOWN_WORKOUT_TYPES = (
    "easy",
    "long",
    "long_run",
    "tempo",
    "threshold",
    "interval",
    "intervals",
    "speed",
    "recovery",
    "progression",
    "race",
)


@dataclass
class WorkoutIntent:
    """Derived intent of the *planned* run, not a verdict on execution."""

    planned_type: Optional[str] = None
    planned_miles: Optional[float] = None
    plan_status: Optional[str] = None  # "executed" | "unplanned" | None
    violated_rest_day: Optional[bool] = None

    @property
    def is_quality_session(self) -> bool:
        """Tempo / threshold / interval / speed / progression / race."""
        t = (self.planned_type or "").strip().lower()
        return t in {
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
        t = (self.planned_type or "").strip().lower()
        return t in {"easy", "recovery", "long", "long_run"}

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
class RunReviewContext:
    """Bundle of facts the LLM may use to review one completed run."""

    activity_id: int
    anchor_local_date: str
    facts: Dict[str, Any] = field(default_factory=dict)
    training_kpis: Optional[Dict[str, Any]] = None
    zone_bounds: Optional[Dict[str, Any]] = None
    hr_drift_band_zones: Optional[Any] = None
    is_easy_run: Optional[bool] = None
    workout_intent: WorkoutIntent = field(default_factory=WorkoutIntent)
    splits: Optional[Dict[str, Any]] = None  # full tool_get_run_splits payload
    splits_truncated: bool = False
    splits_count: int = 0
    hr_profile: Optional[Dict[str, Any]] = None
    evidence_pack: Optional[Dict[str, Any]] = None
    evidence_pack_trace: Optional[Dict[str, Any]] = None
    week_volume: Optional[Dict[str, Any]] = None
    comparison_sessions: Optional[List[Dict[str, Any]]] = None
    resolved_via: str = ""  # "find_runs_by_date" | "most_recent_run" | "hint"
    scope: str = "single_run"  # propagates from classifier

    def to_compact_dict(self, *, for_llm: bool = False) -> Dict[str, Any]:
        """Serialize for embedding inside the system prompt (LLM payload).

        When ``for_llm`` is True, ``training_kpis`` is included except
        ``hr_drift_pct``, ``hr_drift_band``, and ``hr_drift_summary_display``
        (RunSummary drift chip). ``zone_bounds`` and ``hr_drift_band_zones``
        are unchanged. The full ``training_kpis`` remains on the mobile
        ``data`` payload via :func:`run_review.payload.build_payload_data`.
        """
        out: Dict[str, Any] = {
            "activity_id": self.activity_id,
            "anchor_local_date": self.anchor_local_date,
            "scope": self.scope,
            "facts": self.facts,
            "workout_intent": self.workout_intent.to_prompt_dict(),
        }
        if self.training_kpis is not None:
            if for_llm:
                slim = {
                    k: v
                    for k, v in self.training_kpis.items()
                    if k not in _LLM_OMIT_TRAINING_KPI_KEYS
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


def is_known_workout_type(value: Optional[str]) -> bool:
    """Used by tests to confirm the intent vocabulary stays explicit."""
    return (value or "").strip().lower() in _KNOWN_WORKOUT_TYPES
