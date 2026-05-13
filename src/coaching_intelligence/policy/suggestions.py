"""Structured suggestions derived from deficits + allowed actions (Wave 4)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.coaching_intelligence.contracts.deficits import Deficits
from src.coaching_intelligence.contracts.suggestion import SUGGESTION_SCHEMA, Suggestion
from src.coaching_intelligence.policy.demand import compute_demand_score
from src.coaching_intelligence.time_clock import (
    format_clock_seconds,
    parse_clock_seconds,
)

_MARATHON_MILES = 26.2
_MIN_PROPOSED_MARATHON_SEC = 2 * 3600 + 45 * 60  # 2:45:00
_MAX_PROPOSED_MARATHON_SEC = 6 * 3600  # 6:00:00
_FIVE_MIN_SEC = 300
_TRAINING_BLOCK_PACE_GAIN_LONG_SEC_PER_MI = 35.0
_TRAINING_BLOCK_PACE_GAIN_MED_SEC_PER_MI = 25.0
_TRAINING_BLOCK_PACE_GAIN_SHORT_SEC_PER_MI = 15.0


def _proposed_marathon_clock_after_pace_buffer(
    *,
    target_time: Any,
    pace_deficit_sec_per_mi: float,
    weeks_to_race: Optional[float] = None,
) -> Optional[str]:
    base = parse_clock_seconds(target_time)
    if base is None:
        return None
    block_gain = 0.0
    if weeks_to_race is not None:
        if weeks_to_race >= 16:
            block_gain = _TRAINING_BLOCK_PACE_GAIN_LONG_SEC_PER_MI
        elif weeks_to_race >= 10:
            block_gain = _TRAINING_BLOCK_PACE_GAIN_MED_SEC_PER_MI
    adjusted_deficit = max(0.0, float(pace_deficit_sec_per_mi) - block_gain)
    add = int(round(adjusted_deficit * _MARATHON_MILES))
    total = max(
        _MIN_PROPOSED_MARATHON_SEC,
        min(_MAX_PROPOSED_MARATHON_SEC, base + add),
    )
    rounded = int(round(total / float(_FIVE_MIN_SEC))) * _FIVE_MIN_SEC
    rounded = max(
        _MIN_PROPOSED_MARATHON_SEC,
        min(_MAX_PROPOSED_MARATHON_SEC, rounded),
    )
    return format_clock_seconds(rounded)


def _training_days_for_marathon_clock(clock: str) -> tuple[int, int]:
    sec = parse_clock_seconds(clock)
    if sec is None:
        return 4, 5
    demand = compute_demand_score(float(sec) / _MARATHON_MILES, "Marathon")
    if demand >= 0.75:
        return 5, 6
    if demand >= 0.4:
        return 4, 5
    return 3, 4


def realistic_target_from_deficits(
    deficits: Deficits,
    plan_request: Dict[str, Any],
    *,
    weeks_to_race: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Practical target-time recommendation for the compact runner-analysis card."""
    if (
        deficits.pace_deficit_sec_per_mi is None
        or deficits.pace_deficit_sec_per_mi <= 0
    ):
        return None
    rd = str(plan_request.get("race_distance") or "").strip().lower()
    if "marathon" not in rd or "half" in rd:
        return None
    proposed = _proposed_marathon_clock_after_pace_buffer(
        target_time=plan_request.get("target_time"),
        pace_deficit_sec_per_mi=float(deficits.pace_deficit_sec_per_mi),
        weeks_to_race=weeks_to_race,
    )
    if not proposed:
        return None
    min_days, ideal_days = _training_days_for_marathon_clock(proposed)
    return {
        "schema_version": "realistic_target.v1",
        "target_time": proposed,
        "training_days_min": min_days,
        "training_days_ideal": ideal_days,
        "headline": (
            f"Aim around {proposed} this cycle. Train {min_days} days/week minimum; "
            f"{ideal_days} is better."
        ),
        "primary_action": {
            "id": "adjust_goal",
            "label": f"Set goal around {proposed}",
            "chip_updates": {"runner_tradeoff_choice": "adjust_goal"},
        },
    }


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
    *,
    weeks_to_race: Optional[float] = None,
) -> List[Suggestion]:
    """One chip-oriented suggestion per allowed action, plus deficit-aware goal hint."""
    out: List[Suggestion] = []
    seen: set[str] = set()

    pv: Optional[str] = None
    if (
        deficits.pace_deficit_sec_per_mi is not None
        and deficits.pace_deficit_sec_per_mi > 0
    ):
        pv = _proposed_marathon_clock_after_pace_buffer(
            target_time=plan_request.get("target_time"),
            pace_deficit_sec_per_mi=float(deficits.pace_deficit_sec_per_mi),
            weeks_to_race=weeks_to_race,
        )
    has_pace_gap = (
        deficits.pace_deficit_sec_per_mi is not None
        and deficits.pace_deficit_sec_per_mi > 0
    )
    if has_pace_gap and "adjust_goal" not in {
        str(x).strip() for x in allowed_user_actions if x
    }:
        out.append(
            Suggestion(
                schema_version=SUGGESTION_SCHEMA,
                id="adjust_goal",
                label="Adjust the race goal",
                chip_updates={
                    "runner_tradeoff_choice": "adjust_goal",
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
        proposed_value = pv if cid == "adjust_goal" and pv else None
        chip_updates: Dict[str, Any] = {"action": cid}
        if cid == "adjust_goal":
            chip_updates = {"runner_tradeoff_choice": "adjust_goal"}
        out.append(
            Suggestion(
                schema_version=SUGGESTION_SCHEMA,
                id=cid,
                label=_LABELS.get(cid, "Update your plan inputs"),
                chip_updates=chip_updates,
                proposed_value=proposed_value,
            )
        )

    return out
