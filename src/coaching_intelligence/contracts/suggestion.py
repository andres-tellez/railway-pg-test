"""Structured intake / chip suggestion (future phases)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

SUGGESTION_SCHEMA = "suggestion.v1"


@dataclass(frozen=True)
class Suggestion:
    schema_version: str
    id: str
    label: str
    chip_updates: Dict[str, Any]
    proposed_value: Optional[str] = None

    def to_api_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "id": self.id,
            "label": self.label,
            "chip_updates": dict(self.chip_updates),
        }
        if self.proposed_value is not None:
            out["proposed_value"] = self.proposed_value
        return out

    @staticmethod
    def from_api_dict(d: Dict[str, Any]) -> "Suggestion":
        cu = d.get("chip_updates")
        if not isinstance(cu, dict):
            cu = {}
        return Suggestion(
            schema_version=str(d.get("schema_version") or SUGGESTION_SCHEMA),
            id=str(d.get("id") or ""),
            label=str(d.get("label") or ""),
            chip_updates=dict(cu),
            proposed_value=(
                str(d["proposed_value"])
                if d.get("proposed_value") is not None
                else None
            ),
        )
