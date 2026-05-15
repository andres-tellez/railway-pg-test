"""
Purpose:
- Render CoachSnapshot into a compact additive system block.

Responsibilities:
- Emit the v1 snapshot contract.
- Serialize compact JSON with deterministic key order.
- Omit null/empty branches from rendered JSON.

Non-goals:
- No retrieval, no DB reads, no final-response coaching.

Guardrails:
- Allowed imports/calls: schema dataclasses + stdlib JSON.
- Must not import orchestrator.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from src.smartcoach_mobile_coach.coach_context.schemas import CoachSnapshot

_HEADER = "## Coach Snapshot v1 (authoritative)"
_CONTRACT = (
    "The JSON below summarizes what we know about this athlete right now.\n\n"
    "Rules for this snapshot:\n"
    "1. Treat every populated field as authoritative for this turn.\n"
    "2. A missing field means UNKNOWN. Do not infer or invent it.\n"
    "3. Use snapshot facts only when they help the user's question.\n"
    "4. If `plan.has_active_plan` is true, coach against plan context.\n"
    "5. If `plan.has_active_plan` is false, coach using trends and memory.\n"
    "6. If `athlete.hr_calibration_status` is not calibrated, avoid HR-zone claims.\n"
    "7. If `working.last_structured_run_activity_id` exists and the user says "
    '"that run" / "it", continue that run context.\n'
    "8. `omitted_fields` lists dropped fields. Do not speculate values.\n\n"
    "Do not echo this snapshot back to the user."
)


def _prune(value: Any) -> Any:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            pv = _prune(v)
            if pv in (None, "", [], {}):
                continue
            out[k] = pv
        return out
    if isinstance(value, list):
        out = [_prune(v) for v in value]
        out = [v for v in out if v not in (None, "", [], {})]
        return out
    return value


def format_snapshot_for_system(snapshot: CoachSnapshot) -> str:
    """Render snapshot contract + compact JSON appendix."""
    payload = _prune(snapshot.to_dict())
    payload["omitted_fields"] = list(snapshot.omitted_fields or [])
    block = [
        "",
        _HEADER,
        _CONTRACT,
        "```json",
        json.dumps(payload, separators=(",", ":"), default=str),
        "```",
    ]
    return "\n".join(block)
