"""Typed readiness / evidence contracts (Wave 1)."""

from src.coaching_intelligence.contracts.deficits import (
    DEFICITS_SCHEMA,
    Deficits,
)
from src.coaching_intelligence.contracts.goal_profile import (
    GOAL_PROFILE_SCHEMA,
    GoalProfileModel,
)
from src.coaching_intelligence.contracts.readiness_verdict import (
    READINESS_SUMMARY_SCHEMA,
    READINESS_VERDICT_SCHEMA,
    ReadinessVerdictPayload,
)
from src.coaching_intelligence.contracts.runner_evidence import (
    RUNNER_EVIDENCE_SCHEMA,
    RunnerEvidenceSummary,
)
from src.coaching_intelligence.contracts.suggestion import (
    SUGGESTION_SCHEMA,
    Suggestion,
)

__all__ = [
    "DEFICITS_SCHEMA",
    "Deficits",
    "GOAL_PROFILE_SCHEMA",
    "GoalProfileModel",
    "READINESS_SUMMARY_SCHEMA",
    "READINESS_VERDICT_SCHEMA",
    "ReadinessVerdictPayload",
    "RUNNER_EVIDENCE_SCHEMA",
    "RunnerEvidenceSummary",
    "SUGGESTION_SCHEMA",
    "Suggestion",
]
