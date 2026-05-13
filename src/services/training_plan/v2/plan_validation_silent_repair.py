"""
Single-pass silent repair for internally fixable validation errors.

Keeps planner output authoritative: we only adjust the generated plan artifact
to satisfy the existing deterministic validator, then re-run validation once.
No orchestration hooks, no mutation engines — repair rules are an explicit
allowlist keyed by validation ``rule`` codes.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any, Dict, FrozenSet, List, Optional

from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.services.training_plan.v2.plan_validation_service_v2 import (
    PlanValidationServiceV2,
)
from src.services.training_plan.workout_utils import (
    calculate_weekly_mileage_from_workouts,
)

logger = logging.getLogger(__name__)

# Error-level rules we may fix without involving the athlete (allowlist).
_SILENT_REPAIRABLE_RULES: FrozenSet[str] = frozenset(
    {
        "missing_taper",
        "incorrect_taper_weeks",
        "unsafe_long_run_progression",
    }
)


def violations_are_silent_repairable(violations: List[Dict[str, Any]]) -> bool:
    """True if every returned violation is covered by the silent-repair allowlist."""
    if not violations:
        return False
    for v in violations:
        if not isinstance(v, dict):
            return False
        rule = str(v.get("rule") or "")
        if rule not in _SILENT_REPAIRABLE_RULES:
            return False
    return True


def _sorted_weeks(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    weeks = plan.get("weeks")
    if not isinstance(weeks, list):
        return []
    return sorted(
        [w for w in weeks if isinstance(w, dict)],
        key=lambda w: int(w.get("week_number") or 0),
    )


def _apply_taper_phase_labels(plan: Dict[str, Any], config: RaceDistanceConfig) -> None:
    tw = int(config.taper_weeks)
    sw = _sorted_weeks(plan)
    if len(sw) < tw:
        return
    for w in sw[-tw:]:
        w["phase"] = "Taper"


def _scale_week_workouts_to_weekly_total(
    week: Dict[str, Any], target_total: float
) -> None:
    workouts = week.get("workouts")
    if not isinstance(workouts, list) or not workouts:
        week["weekly_mileage"] = round(float(target_total), 1)
        return
    current = float(calculate_weekly_mileage_from_workouts(workouts))
    if current <= 0:
        week["weekly_mileage"] = round(float(target_total), 1)
        return
    factor = float(target_total) / current
    for w in workouts:
        if not isinstance(w, dict):
            continue
        for key in ("miles", "distance_miles"):
            if w.get(key) is not None:
                try:
                    w[key] = round(float(w[key]) * factor, 2)
                except (TypeError, ValueError):
                    pass
    week["weekly_mileage"] = round(calculate_weekly_mileage_from_workouts(workouts), 1)


def _apply_taper_volume_from_ratios(
    plan: Dict[str, Any], config: RaceDistanceConfig
) -> None:
    """Reduce last ``taper_weeks`` weekly totals toward ``taper_ratios`` vs pre-taper week."""
    tw = int(config.taper_weeks)
    ratios = list(config.taper_ratios)
    sw = _sorted_weeks(plan)
    if len(sw) < tw + 1 or len(ratios) != tw:
        return

    pre_taper = sw[-tw - 1]
    pre_m = pre_taper.get("weekly_mileage")
    try:
        pre_m_f = float(pre_m)
    except (TypeError, ValueError):
        return
    if pre_m_f <= 0:
        return

    taper_block = sw[-tw:]
    for i, week in enumerate(taper_block):
        target = pre_m_f * float(ratios[i])
        _scale_week_workouts_to_weekly_total(week, target)


def _week_number_from_violation(v: Dict[str, Any]) -> Optional[int]:
    m = re.search(r"week\s+(\d+)", str(v.get("location") or ""), flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return None


def _max_long_run_from_violation(v: Dict[str, Any]) -> Optional[float]:
    suggestion = str(v.get("suggestion") or "")
    m = re.search(r"at\s+most\s+(\d+(?:\.\d+)?)", suggestion, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        out = float(m.group(1))
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _apply_long_run_progression_repair(
    plan: Dict[str, Any],
    violations: List[Dict[str, Any]],
) -> None:
    week_map = {
        int(w.get("week_number") or 0): w
        for w in _sorted_weeks(plan)
        if int(w.get("week_number") or 0) > 0
    }
    for v in violations:
        if (
            not isinstance(v, dict)
            or str(v.get("rule") or "") != "unsafe_long_run_progression"
        ):
            continue
        week_number = _week_number_from_violation(v)
        max_long_run = _max_long_run_from_violation(v)
        if week_number is None or max_long_run is None:
            continue
        week = week_map.get(week_number)
        if not isinstance(week, dict):
            continue
        workouts = week.get("workouts")
        if not isinstance(workouts, list):
            continue
        changed = False
        for workout in workouts:
            if not isinstance(workout, dict):
                continue
            workout_type = str(workout.get("workout_type") or "").strip().lower()
            if workout_type not in ("long run", "long"):
                continue
            try:
                d = float(workout.get("distance_miles", 0) or 0)
            except (TypeError, ValueError):
                continue
            if d <= max_long_run:
                continue
            workout["distance_miles"] = round(max_long_run, 2)
            if workout.get("miles") is not None:
                workout["miles"] = round(max_long_run, 2)
            changed = True
        if changed:
            week["weekly_mileage"] = round(
                calculate_weekly_mileage_from_workouts(workouts), 1
            )


def attempt_silent_repair_then_revalidate(
    plan: Dict[str, Any],
    violations: List[Dict[str, Any]],
    *,
    config: RaceDistanceConfig,
    unit_system: str,
) -> Optional[Dict[str, Any]]:
    """
    One repair attempt + single re-validation.

    Returns a full validation dict (same shape as PlanValidationServiceV2.validate_plan)
    if repair + validation succeed; otherwise None.
    """
    if not violations_are_silent_repairable(violations):
        return None

    rules = {str(v.get("rule") or "") for v in violations if isinstance(v, dict)}
    fixed = copy.deepcopy(plan)

    if "incorrect_taper_weeks" in rules:
        _apply_taper_phase_labels(fixed, config)
    if "missing_taper" in rules:
        _apply_taper_volume_from_ratios(fixed, config)
    if "unsafe_long_run_progression" in rules:
        _apply_long_run_progression_repair(fixed, violations)

    validator = PlanValidationServiceV2(config=config, unit_system=unit_system)
    re_val = validator.validate_plan(fixed, unit_system=unit_system)
    if re_val.get("valid") and re_val.get("validated_plan"):
        logger.info(
            "[plan_validation_silent_repair] success rules=%s",
            sorted(rules),
        )
        return re_val

    logger.info(
        "[plan_validation_silent_repair] revalidate_failed rules=%s violations=%s",
        sorted(rules),
        [v.get("rule") for v in (re_val.get("violations") or [])],
    )
    return None
