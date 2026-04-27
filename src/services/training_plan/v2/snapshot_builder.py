"""Lightweight, deterministic snapshots for plan persistence (no generation)."""

from __future__ import annotations

from typing import Any, Dict


def build_snapshot_from_approval(
    validation: Dict[str, Any], plan_metadata: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "validation": validation,
        "spine_quality_issues": [],
        "decision_trace": [],
        "metadata": {
            "source": "approve",
            "plan_name": plan_metadata.get("plan_name"),
            "race_date": plan_metadata.get("race_date"),
        },
    }
