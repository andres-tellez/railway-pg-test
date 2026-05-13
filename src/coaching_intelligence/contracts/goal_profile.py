"""Goal profile contract (optional fields for future demand scoring)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

GOAL_PROFILE_SCHEMA = "goal_profile.v1"


@dataclass(frozen=True)
class GoalProfileModel:
    schema_version: str
    primary_goal: Optional[str] = None
    race_distance: Optional[str] = None
    target_time: Optional[str] = None
    profile_tag: Optional[str] = None
    demand_score: Optional[float] = None

    def to_api_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"schema_version": self.schema_version}
        if self.primary_goal is not None:
            out["primary_goal"] = self.primary_goal
        if self.race_distance is not None:
            out["race_distance"] = self.race_distance
        if self.target_time is not None:
            out["target_time"] = self.target_time
        if self.profile_tag is not None:
            out["profile_tag"] = self.profile_tag
        if self.demand_score is not None:
            out["demand_score"] = self.demand_score
        return out

    @staticmethod
    def from_api_dict(d: Dict[str, Any]) -> "GoalProfileModel":
        return GoalProfileModel(
            schema_version=str(d.get("schema_version") or GOAL_PROFILE_SCHEMA),
            primary_goal=(
                str(d["primary_goal"]) if d.get("primary_goal") is not None else None
            ),
            race_distance=(
                str(d["race_distance"]) if d.get("race_distance") is not None else None
            ),
            target_time=(
                str(d["target_time"]) if d.get("target_time") is not None else None
            ),
            profile_tag=(
                str(d["profile_tag"]) if d.get("profile_tag") is not None else None
            ),
            demand_score=_as_optional_float(d.get("demand_score")),
        )


def _as_optional_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
