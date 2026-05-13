"""Single-field consistency checks after merges (Phase 7.1)."""

from __future__ import annotations

from typing import Any, Dict, List


def validate_long_run_matches_training_days(
    draft: Dict[str, Any],
    errors: List[str],
) -> None:
    if "training_days" in draft and draft.get("long_run_day"):
        tdays = draft.get("training_days") or []
        if draft["long_run_day"] not in tdays:
            errors.append("long_run_day must be one of training_days.")
