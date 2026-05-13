"""Axis deficits for readiness (future phases populate; Wave 1 = empty defaults)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

DEFICITS_SCHEMA = "deficits.v1"


@dataclass(frozen=True)
class Deficits:
    schema_version: str
    pace_deficit_sec_per_mi: Optional[float] = None
    volume_deficit_mpw: Optional[float] = None
    long_run_deficit_mi: Optional[float] = None
    time_deficit_weeks: Optional[float] = None
    frequency_deficit_days: Optional[float] = None

    def to_api_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"schema_version": self.schema_version}
        for k, v in (
            ("pace_deficit_sec_per_mi", self.pace_deficit_sec_per_mi),
            ("volume_deficit_mpw", self.volume_deficit_mpw),
            ("long_run_deficit_mi", self.long_run_deficit_mi),
            ("time_deficit_weeks", self.time_deficit_weeks),
            ("frequency_deficit_days", self.frequency_deficit_days),
        ):
            if v is not None:
                out[k] = v
        return out

    @staticmethod
    def from_api_dict(d: Dict[str, Any]) -> "Deficits":
        return Deficits(
            schema_version=str(d.get("schema_version") or DEFICITS_SCHEMA),
            pace_deficit_sec_per_mi=_opt_float(d.get("pace_deficit_sec_per_mi")),
            volume_deficit_mpw=_opt_float(d.get("volume_deficit_mpw")),
            long_run_deficit_mi=_opt_float(d.get("long_run_deficit_mi")),
            time_deficit_weeks=_opt_float(d.get("time_deficit_weeks")),
            frequency_deficit_days=_opt_float(d.get("frequency_deficit_days")),
        )


def _opt_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
