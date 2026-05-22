"""Draft response payload helpers for plan generation endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional


def build_standard_draft_payload(
    *,
    validation_result: Dict[str, Any],
    timezone: Optional[str] = None,
    context_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert planner validation output into frontend-friendly draft payload."""
    generated_plan = validation_result.get("draft") or validation_result.get(
        "validated_plan"
    )
    if generated_plan and timezone:
        generated_plan = {**generated_plan, "timezone": timezone}

    validation_block: Dict[str, Any] = {
        "valid": bool(validation_result.get("valid")),
        "violations": validation_result.get("violations", []),
        "validated_plan": validation_result.get("validated_plan"),
        "decision_trace": validation_result.get("decision_trace", []),
        "spine_quality": validation_result.get("spine_quality"),
    }
    if context_snapshot is not None:
        validation_block["context_snapshot"] = context_snapshot

    draft_payload: Dict[str, Any] = {
        "generated_plan": generated_plan or {},
        "validation": validation_block,
        "recovery_metadata": validation_result.get("recovery_metadata"),
        "pass1_rationale": validation_result.get("pass1_rationale"),
        "race_date_validation": validation_result.get("race_date_validation"),
    }

    # Backward compatibility for clients expecting beta payload keys.
    draft_payload["draft"] = draft_payload["generated_plan"]
    draft_payload["valid"] = draft_payload["validation"]["valid"]
    draft_payload["violations"] = draft_payload["validation"]["violations"]
    draft_payload["raw_result"] = validation_result
    return draft_payload
