"""Lossless wrap of plan-intake activity summary dict for typed boundaries (Wave 1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

RUNNER_EVIDENCE_SCHEMA = "runner_evidence.v1"


@dataclass(frozen=True)
class RunnerEvidenceSummary:
    """Activity snapshot as returned by ``compute_plan_intake_activity_summary``."""

    schema_version: str
    data: Dict[str, Any]

    def to_api_dict(self) -> Dict[str, Any]:
        out = dict(self.data)
        out["schema_version"] = self.schema_version
        return out

    @staticmethod
    def from_activity_summary(d: Dict[str, Any]) -> "RunnerEvidenceSummary":
        payload = {k: v for k, v in d.items() if k != "schema_version"}
        return RunnerEvidenceSummary(
            schema_version=RUNNER_EVIDENCE_SCHEMA,
            data=payload,
        )

    @staticmethod
    def from_api_dict(d: Dict[str, Any]) -> "RunnerEvidenceSummary":
        ver = str(d.get("schema_version") or RUNNER_EVIDENCE_SCHEMA)
        payload = {k: v for k, v in d.items() if k != "schema_version"}
        return RunnerEvidenceSummary(schema_version=ver, data=payload)
