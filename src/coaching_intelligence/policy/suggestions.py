"""Structured suggestions derived from deficits + allowed actions (Wave 4)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.coaching_intelligence.contracts.deficits import Deficits
from src.coaching_intelligence.contracts.suggestion import SUGGESTION_SCHEMA, Suggestion

_MARATHON_MILES = 26.2


def _format_clock_seconds(secs: int) -> str:
    secs = max(0, int(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _proposed_marathon_clock_after_pace_buffer(
    *,
    target_time: Any,
    pace_deficit_sec_per_mi: float,
) -> Optional[str]:
    from src.coaching_intelligence.plan_generation_readiness import (
        _parse_clock_seconds,
    )

    base = _parse_clock_seconds(target_time)
    if base is None:
        return None
    add = int(round(float(pace_deficit_sec_per_mi) * _MARATHON_MILES))
    return _format_clock_seconds(base + add)


_LABELS: Dict[str, str] = {
    "adjust_goal": "Adjust the race goal",
    "adjust_timeline": "Move the race date",
    "add_running_day": "Add a weekly running day",
    "build_base_first": "Build base fitness first",
    "collect_more_activity_data": "Sync more running history",
    "complete_alignment_questions": "Answer the remaining intake questions",
    "ingest_more_activity": "Add more activity data",
}


def derive_suggestions(
    deficits: Deficits,
    plan_request: Dict[str, Any],
    allowed_user_actions: Sequence[str],
) -> List[Suggestion]:
    """One chip-oriented suggestion per allowed action, plus deficit-aware goal hint."""
    out: List[Suggestion] = []
    seen: set[str] = set()

    if (
        deficits.pace_deficit_sec_per_mi is not None
        and deficits.pace_deficit_sec_per_mi > 0
        and "adjust_goal" not in {str(x).strip() for x in allowed_user_actions if x}
    ):
        pv = _proposed_marathon_clock_after_pace_buffer(
            target_time=plan_request.get("target_time"),
            pace_deficit_sec_per_mi=float(deficits.pace_deficit_sec_per_mi),
        )
        out.append(
            Suggestion(
                schema_version=SUGGESTION_SCHEMA,
                id="adjust_goal",
                label="Soften the time goal to close the easy-pace gap",
                chip_updates={
                    "hint": "pace_deficit_sec_per_mi",
                    "value": deficits.pace_deficit_sec_per_mi,
                },
                proposed_value=pv,
            )
        )
        seen.add("adjust_goal")

    for raw in allowed_user_actions:
        cid = str(raw or "").strip()
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(
            Suggestion(
                schema_version=SUGGESTION_SCHEMA,
                id=cid,
                label=_LABELS.get(cid, "Update your plan inputs"),
                chip_updates={"action": cid},
                proposed_value=None,
            )
        )

    return out
