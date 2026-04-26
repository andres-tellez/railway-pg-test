"""Central read-only validation for long-run curves (Stage B).

All checks return structured issues; callers decide whether to raise, log, or
self-correct. Thresholds default to legacy spine / Pass1 constants and can be
overridden via optional attributes on ``RaceDistanceConfig`` (``getattr``).

-------------------------------------------------------------------------------
DEPRECATED COMPONENTS (legacy wrappers / paths — still required at runtime)

Canonical replacement: :func:`validate_long_run_curve` with explicit selector
flags and overrides. **Do not delete** until Phase 3 Stage D without migrating
every call site below.

Registry (remove in Stage D after migration):

- ``src.services.training_plan.v2.marathon.pass1_longrun_first_v2.validate_spine``
  — thin Pass1 helper; callers should invoke ``validate_long_run_curve`` directly
  with ``include_pass1_progression=True`` (and explicit kwargs).

- ``src.services.training_plan.v2.shared_v2.long_run_spine_v2.validate_phase_quality``
  — (bool, str list) facade over ``validate_long_run_curve`` phase-quality only;
  replace with structured issues + single API.

- ``plan_generation_orchestrator_v2.PlanGenerationOrchestratorV2._validate_spine_immutability``
  — orchestrator-only guardrail wrapper; fold into direct
  ``validate_long_run_curve`` orchestration entry.

- ``src.services.training_plan.v2.shared_v2.long_run_spine_v2`` **in-spine
  mutation** inside ``_generate_long_run_spine`` (e.g. fixed-length tail):
  post-build edits to ``long_run_miles``, :func:`assign_training_intent_phases`
  in-place phase labels, and attaching ``global_peak_week_number`` /
  ``peak_block_peak_week_number`` on week dicts. TODO Stage D: immutable spine
  construction + separate labeling/metadata pass.

See module docstring in ``long_run_spine_v2`` for a pointer to this registry.
-------------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional, TypedDict

from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.services.training_plan.v2.shared_v2.rounding_utils import round_to_half_mile

logger = logging.getLogger(__name__)


class LongRunCurveIssue(TypedDict):
    """Single validation finding (read-only; no mutation of inputs)."""

    code: str
    severity: Literal["error", "warning"]
    message: str
    details: Dict[str, Any]


def _thresholds(config: RaceDistanceConfig) -> Dict[str, float | int]:
    """Config-driven thresholds with legacy defaults (``getattr`` on config)."""
    return {
        "phase_cutback_drop_mi": float(
            getattr(config, "curve_validation_phase_cutback_drop_mi", 0.5)
        ),
        "pass1_cutback_flag_drop_mi": float(
            getattr(config, "curve_validation_pass1_cutback_flag_drop_mi", 0.25)
        ),
        "aggressive_jump_mi": float(
            getattr(config, "curve_validation_aggressive_jump_mi", 3.0)
        ),
        "taper_increase_tolerance_mi": float(
            getattr(config, "curve_validation_taper_increase_tolerance_mi", 1.0)
        ),
        "peak_reach_tolerance_mi": float(
            getattr(config, "curve_validation_peak_reach_tolerance_mi", 1.0)
        ),
        "immutability_peak_margin_mi": float(
            getattr(config, "curve_validation_immutability_peak_margin_mi", 1.0)
        ),
        "resume_week_hi_extra_mi": float(
            getattr(config, "curve_validation_resume_week_hi_extra_mi", 3.0)
        ),
        "min_taper_weeks_display": int(
            getattr(config, "curve_validation_min_taper_weeks_display", 2)
        ),
    }


def _issue(
    code: str,
    severity: Literal["error", "warning"],
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> LongRunCurveIssue:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "details": details or {},
    }


def _structure_field_issues(
    spine_rows: List[Dict[str, Any]]
) -> List[LongRunCurveIssue]:
    """Week dict structure (``_validate_spine_immutability`` field checks)."""
    issues: List[LongRunCurveIssue] = []
    for i, week in enumerate(spine_rows):
        if "long_run_miles" not in week:
            issues.append(
                _issue(
                    "structure_missing_long_run",
                    "error",
                    f"Week {i + 1} is missing long run distance data.",
                    {"week_index": i + 1},
                )
            )
            return issues
        if "phase" not in week:
            issues.append(
                _issue(
                    "structure_missing_phase",
                    "error",
                    f"Week {i + 1} is missing training phase data.",
                    {"week_index": i + 1},
                )
            )
            return issues
        lr = float(week.get("long_run_miles", 0) or 0)
        if lr <= 0:
            issues.append(
                _issue(
                    "structure_invalid_long_run",
                    "error",
                    f"Week {i + 1} has an invalid long run distance.",
                    {"week_index": i + 1, "long_run_miles": lr},
                )
            )
            return issues
    return issues


def _peak_max_issue(
    curve: List[float], peak_target: float, thr: Dict[str, float | int]
) -> List[LongRunCurveIssue]:
    """Max long run vs adaptive peak floor (``_validate_spine_immutability`` tail)."""
    max_lr = max(float(x) for x in curve)
    margin = float(thr["immutability_peak_margin_mi"])
    min_required = float(peak_target) - margin
    if max_lr < min_required:
        return [
            _issue(
                "peak_not_reached_max_below_target",
                "error",
                (
                    "The long-run progression did not reach the adaptive peak "
                    "expected for this runner and schedule."
                ),
                {
                    "max_long_run_miles": max_lr,
                    "adaptive_peak_miles": float(peak_target),
                    "min_required_max_long_run_miles": min_required,
                },
            )
        ]
    return []


def _pass1_progression_issues(
    curve: List[float],
    spine_rows: List[Dict[str, Any]],
    *,
    expected_start: float,
    peak: float,
    inc: float,
    taper_weeks: int,
    thr: Dict[str, float | int],
) -> List[LongRunCurveIssue]:
    """Logic from ``validate_spine`` in ``pass1_longrun_first_v2`` (raise → issues)."""
    issues: List[LongRunCurveIssue] = []
    if not curve or not spine_rows or len(curve) != len(spine_rows):
        if not curve:
            issues.append(_issue("pass1_empty_curve", "error", "LR spine empty", {}))
        return issues

    if abs(float(spine_rows[0].get("long_run_miles", 0)) - expected_start) > 1e-6:
        issues.append(
            _issue(
                "pass1_week1_mismatch",
                "error",
                (
                    f"Week 1 mismatch: got {spine_rows[0].get('long_run_miles', 0):.1f}, "
                    f"expected {expected_start:.1f} (stable week-1 rule)"
                ),
                {
                    "expected_start": expected_start,
                    "actual": float(spine_rows[0].get("long_run_miles", 0)),
                },
            )
        )
        return issues

    taper_w = int(taper_weeks)
    pre_n = max(1, len(curve) - taper_w)
    peaked = False
    drop_tol = float(thr["pass1_cutback_flag_drop_mi"])
    resume_hi_extra = float(thr["resume_week_hi_extra_mi"])

    for i in range(1, len(curve)):
        lr_prev = float(spine_rows[i - 1].get("long_run_miles", 0))
        lr = float(spine_rows[i].get("long_run_miles", 0))
        lr_two_back = (
            float(spine_rows[i - 2].get("long_run_miles", 0)) if i - 2 >= 0 else lr_prev
        )
        wn = int(spine_rows[i].get("week_number") or (i + 1))

        if i < pre_n:
            cap = peak if not peaked else max(0.0, peak - 1.0)
            is_cb = bool(spine_rows[i].get("is_cutback"))
            prev_cb = bool(spine_rows[i - 1].get("is_cutback"))
            if is_cb:
                if not (lr < lr_prev - drop_tol):
                    issues.append(
                        _issue(
                            "pass1_cutback_flag_invalid",
                            "error",
                            (
                                f"Week {wn}: cutback flag set but long run not below prior "
                                f"({lr_prev:.1f} → {lr:.1f})"
                            ),
                            {"week_number": wn, "lr_prev": lr_prev, "lr": lr},
                        )
                    )
                    return issues
            elif prev_cb:
                lo = round_to_half_mile(lr_prev + inc)
                hi = round_to_half_mile(min(cap, lr_prev + resume_hi_extra))
                if lr < lo - 1e-6 or lr > hi + 1e-6:
                    issues.append(
                        _issue(
                            "pass1_resume_invalid",
                            "error",
                            (
                                f"Week {wn} invalid resume: got {lr:.1f}, expected between "
                                f"{lo:.1f} and {hi:.1f} (after cutback {lr_prev:.1f})"
                            ),
                            {
                                "week_number": wn,
                                "lr": lr,
                                "lo": lo,
                                "hi": hi,
                                "lr_prev": lr_prev,
                            },
                        )
                    )
                    return issues
            else:
                expected = round_to_half_mile(min(cap, lr_prev + inc))
                if abs(lr - expected) > 1e-6:
                    issues.append(
                        _issue(
                            "pass1_week_invalid",
                            "error",
                            (
                                f"Week {wn} invalid: got {lr:.1f}, expected {expected:.1f} "
                                f"(prev {lr_prev:.1f}, two_back {lr_two_back:.1f}, cap {cap:.1f})"
                            ),
                            {
                                "week_number": wn,
                                "lr": lr,
                                "expected": expected,
                                "lr_prev": lr_prev,
                                "lr_two_back": lr_two_back,
                                "cap": cap,
                            },
                        )
                    )
                    return issues
            if not peaked and lr >= peak - 1e-6:
                peaked = True
        else:
            if lr > peak + 1e-6:
                issues.append(
                    _issue(
                        "pass1_taper_exceeds_peak",
                        "error",
                        f"Taper week {wn} exceeds peak: {lr:.1f} > {peak:.1f}",
                        {"week_number": wn, "lr": lr, "peak": peak},
                    )
                )
                return issues
    return issues


def _phase_quality_issues(
    lr_values: List[float],
    *,
    peak: float,
    cutback_every: int,
    taper_weeks: int,
    taper_ratios: List[float],
    thr: Dict[str, float | int],
    total_week_index_for_taper_messages: int,
) -> List[LongRunCurveIssue]:
    """Logic from ``validate_phase_quality`` in ``long_run_spine_v2`` (strings → issues)."""
    issues: List[LongRunCurveIssue] = []
    if not lr_values:
        issues.append(
            _issue("phase_empty_curve", "warning", "Empty spine", {"source": "phase"})
        )
        return issues

    cutback_drop = float(thr["phase_cutback_drop_mi"])
    aggressive_jump = float(thr["aggressive_jump_mi"])
    taper_tol = float(thr["taper_increase_tolerance_mi"])
    peak_reach_tol = float(thr["peak_reach_tolerance_mi"])
    min_taper_weeks = int(thr["min_taper_weeks_display"])

    peak_idx = lr_values.index(max(lr_values))
    build_phase = lr_values[: peak_idx + 1]
    post_peak_phase = (
        lr_values[peak_idx + 1 : -taper_weeks]
        if taper_weeks > 0
        else lr_values[peak_idx + 1 :]
    )
    if taper_weeks > 0:
        taper_start_idx = max(peak_idx + 1, len(lr_values) - taper_weeks)
        taper_phase = lr_values[taper_start_idx:]
    else:
        taper_phase = []

    if build_phase:
        cutback_weeks: List[int] = []
        build_week_numbers: List[int] = []
        build_counter = 0
        for i in range(1, len(build_phase)):
            build_counter += 1
            if build_phase[i] < build_phase[i - 1] - cutback_drop:
                cutback_weeks.append(i + 1)
                build_week_numbers.append(build_counter)

        for i in range(1, len(build_phase)):
            if build_phase[i] < build_phase[i - 1] - cutback_drop:
                if i > 1 and build_phase[i - 1] < build_phase[i - 2] - cutback_drop:
                    issues.append(
                        _issue(
                            "phase_consecutive_cutbacks",
                            "warning",
                            (
                                f"Phase 1 (Build): CONSECUTIVE CUTBACKS detected at weeks {i} and {i+1} "
                                f"({build_phase[i-2]:.1f} → {build_phase[i-1]:.1f} → {build_phase[i]:.1f})"
                            ),
                            {"build_index": i},
                        )
                    )

        if len(build_week_numbers) > 1:
            for j in range(len(build_week_numbers) - 1):
                spacing = build_week_numbers[j + 1] - build_week_numbers[j]
                if spacing != cutback_every:
                    issues.append(
                        _issue(
                            "phase_cutback_spacing",
                            "warning",
                            (
                                f"Phase 1 (Build): Cutback spacing violation - "
                                f"Cutback at build week {build_week_numbers[j]} (Week {cutback_weeks[j]}) "
                                f"followed by cutback at build week {build_week_numbers[j + 1]} "
                                f"(Week {cutback_weeks[j+1]}) "
                                f"(spacing: {spacing} weeks, expected: {cutback_every} weeks)"
                            ),
                            {"spacing": spacing, "expected": cutback_every},
                        )
                    )

        if len(build_week_numbers) > 0:
            first_cutback_week = build_week_numbers[0]
            expected_first_cutback = cutback_every
            if first_cutback_week != expected_first_cutback:
                issues.append(
                    _issue(
                        "phase_first_cutback_timing",
                        "warning",
                        (
                            f"Phase 1 (Build): First cutback at build week {first_cutback_week} "
                            f"(Week {cutback_weeks[0]}), expected at build week {expected_first_cutback}"
                        ),
                        {
                            "first_cutback_week": first_cutback_week,
                            "expected": expected_first_cutback,
                        },
                    )
                )

        cutback_count = len(cutback_weeks)
        build_weeks = len(build_phase) - 1
        min_cutbacks = 1 if build_weeks > cutback_every else 0
        expected_cutbacks = max(min_cutbacks, build_weeks // cutback_every)

        if cutback_count < (expected_cutbacks - 1):
            issues.append(
                _issue(
                    "phase_cutback_count",
                    "warning",
                    (
                        f"Phase 1 (Build): Only {cutback_count} cutbacks found, expected ~{expected_cutbacks} "
                        f"(every {cutback_every} build weeks)"
                    ),
                    {
                        "cutback_count": cutback_count,
                        "expected_cutbacks": expected_cutbacks,
                    },
                )
            )

        for i in range(1, len(build_phase)):
            if build_phase[i] > build_phase[i - 1]:
                jump = build_phase[i] - build_phase[i - 1]
                if i > 1 and build_phase[i - 2] <= build_phase[i - 1]:
                    if jump > aggressive_jump:
                        issues.append(
                            _issue(
                                "phase_aggressive_jump",
                                "warning",
                                (
                                    f"Phase 1 (Build): Week {i+1} aggressive jump of {jump:.1f} miles "
                                    f"(limit: {aggressive_jump:.1f})"
                                ),
                                {"jump": jump, "limit": aggressive_jump},
                            )
                        )

        if build_phase[-1] < peak - peak_reach_tol:
            issues.append(
                _issue(
                    "phase_peak_not_reached_in_build",
                    "warning",
                    (
                        f"Phase 1 (Build): Never reached peak (max: {build_phase[-1]:.1f}, "
                        f"target: {peak:.1f})"
                    ),
                    {"max_build": build_phase[-1], "peak": peak},
                )
            )

    if post_peak_phase:
        for i in range(1, len(post_peak_phase)):
            if post_peak_phase[i] > post_peak_phase[i - 1]:
                week_num = peak_idx + 1 + i + 1
                issues.append(
                    _issue(
                        "phase_post_peak_increase",
                        "warning",
                        (
                            f"Phase 2 (Post-Peak): Week {week_num} increases after peak "
                            f"({post_peak_phase[i-1]:.1f} → {post_peak_phase[i]:.1f})"
                        ),
                        {"week_number": week_num},
                    )
                )
        for i, lr in enumerate(post_peak_phase):
            if lr > peak:
                week_num = peak_idx + 1 + i + 1
                issues.append(
                    _issue(
                        "phase_post_peak_exceeds_peak",
                        "warning",
                        (
                            f"Phase 2 (Post-Peak): Week {week_num} exceeds peak "
                            f"({lr:.1f} > {peak:.1f})"
                        ),
                        {"week_number": week_num, "lr": lr, "peak": peak},
                    )
                )

    if taper_phase:
        if len(taper_phase) < min_taper_weeks:
            issues.append(
                _issue(
                    "phase_taper_too_short",
                    "warning",
                    (
                        f"Phase 3 (Taper): Too short ({len(taper_phase)} weeks, "
                        f"minimum: {min_taper_weeks})"
                    ),
                    {"len_taper": len(taper_phase), "minimum": min_taper_weeks},
                )
            )
        for i in range(1, len(taper_phase)):
            if taper_phase[i] > taper_phase[i - 1] + taper_tol:
                week_num = (
                    total_week_index_for_taper_messages - len(taper_phase) + i + 1
                )
                issues.append(
                    _issue(
                        "phase_taper_increase",
                        "warning",
                        (
                            f"Phase 3 (Taper): Week {week_num} increases significantly "
                            f"({taper_phase[i-1]:.1f} → {taper_phase[i]:.1f})"
                        ),
                        {"week_number": week_num, "tolerance": taper_tol},
                    )
                )

    _ = taper_ratios
    return issues


def validate_long_run_curve(
    curve: List[float],
    config: RaceDistanceConfig,
    *,
    spine_rows: Optional[List[Dict[str, Any]]] = None,
    expected_start_miles: Optional[float] = None,
    peak_target_miles: Optional[float] = None,
    taper_ratios_override: Optional[List[float]] = None,
    cutback_every_override: Optional[int] = None,
    taper_weeks_override: Optional[int] = None,
    include_structure_checks: bool = True,
    include_peak_max_check: bool = True,
    include_pass1_progression: bool = True,
    include_phase_quality: bool = True,
) -> List[LongRunCurveIssue]:
    """Validate a long-run mile curve (and optional week metadata).

    This is the **supported** long-term validation API (not deprecated). Legacy
    wrappers listed under *DEPRECATED COMPONENTS* in this module's docstring
    delegate here.

    Read-only: does not mutate ``curve``, ``config``, or ``spine_rows``.

    **Internal contract (production call sites):** pass ``curve``, ``config``,
    ``spine_rows`` when week dicts exist, and explicit ``*_override`` / selector
    flags so behavior does not depend on this function's defaults. When
    ``include_structure_checks`` is true, ``spine_rows`` must be present and
    aligned with ``curve``. When ``include_pass1_progression`` is true,
    ``spine_rows`` and ``expected_start_miles`` must be set and aligned with
    ``curve``. Missing inputs are logged (checks that need them are skipped as
    before).

    Selectors mirror legacy call sites (those entry points are deprecated for
    Stage D removal): orchestrator immutability (structure + peak max), Pass1
    ``validate_spine``, and ``validate_phase_quality``.
    """
    if include_structure_checks and spine_rows is None:
        logger.warning(
            "validate_long_run_curve: include_structure_checks=True but spine_rows "
            "is None; structure checks are skipped (contract: pass spine_rows)."
        )
    if include_pass1_progression and (
        expected_start_miles is None or spine_rows is None
    ):
        logger.warning(
            "validate_long_run_curve: include_pass1_progression=True but "
            "expected_start_miles or spine_rows is None; Pass1 progression checks "
            "are skipped (contract: pass both, same length as curve)."
        )
    elif (
        include_pass1_progression
        and spine_rows is not None
        and len(spine_rows) != len(curve)
    ):
        logger.warning(
            "validate_long_run_curve: include_pass1_progression=True but "
            "len(spine_rows) != len(curve); progression checks are skipped until "
            "lengths match."
        )

    thr = _thresholds(config)
    peak_t = (
        float(peak_target_miles)
        if peak_target_miles is not None
        else float(config.target_peak_miles)
    )
    taper_ratios = (
        list(taper_ratios_override)
        if taper_ratios_override is not None
        else list(config.taper_ratios)
    )
    cutback_eff = (
        int(cutback_every_override)
        if cutback_every_override is not None
        else int(config.cutback_every)
    )
    taper_weeks_eff = (
        int(taper_weeks_override)
        if taper_weeks_override is not None
        else int(config.taper_weeks)
    )

    out: List[LongRunCurveIssue] = []

    if not curve:
        return [
            _issue(
                "spine_empty",
                "error",
                "The training plan spine has no weeks.",
                {},
            )
        ]

    if include_structure_checks:
        if spine_rows is None:
            pass
        elif len(spine_rows) != len(curve):
            out.append(
                _issue(
                    "structure_row_count_mismatch",
                    "error",
                    "Spine row count does not match curve length.",
                    {"len_curve": len(curve), "len_rows": len(spine_rows)},
                )
            )
            return out
        else:
            struct = _structure_field_issues(spine_rows)
            out.extend(struct)
            if struct:
                return out

    if include_pass1_progression:
        if expected_start_miles is not None and spine_rows is not None:
            if len(spine_rows) == len(curve):
                p1 = _pass1_progression_issues(
                    curve,
                    spine_rows,
                    expected_start=float(expected_start_miles),
                    peak=peak_t,
                    inc=float(config.long_run_increment),
                    taper_weeks=taper_weeks_eff,
                    thr=thr,
                )
                out.extend(p1)
                if any(i["severity"] == "error" for i in p1):
                    return out

    if include_peak_max_check:
        pm = _peak_max_issue(curve, peak_t, thr)
        out.extend(pm)
        if any(i["severity"] == "error" for i in pm):
            return out

    if include_phase_quality:
        out.extend(
            _phase_quality_issues(
                list(curve),
                peak=peak_t,
                cutback_every=cutback_eff,
                taper_weeks=taper_weeks_eff,
                taper_ratios=taper_ratios,
                thr=thr,
                total_week_index_for_taper_messages=len(curve),
            )
        )

    return out


def orchestrator_issue_to_violation_dict(issue: LongRunCurveIssue) -> Dict[str, Any]:
    """Map a ``LongRunCurveIssue`` to ``PlanGenerationOrchestratorV2`` violation shape."""
    code = issue["code"]
    details = dict(issue.get("details") or {})
    if code == "spine_empty":
        return {
            "rule": "spine_empty",
            "severity": "error",
            "location": "plan_generation",
            "failure_code": "spine_empty",
            "failure_reason": issue["message"],
            "details": {},
        }
    if code == "structure_missing_long_run":
        return {
            "rule": "spine_structure",
            "severity": "error",
            "location": "plan_generation",
            "failure_code": "spine_missing_long_run",
            "failure_reason": issue["message"],
            "details": {"week_index": details.get("week_index")},
        }
    if code == "structure_missing_phase":
        return {
            "rule": "spine_structure",
            "severity": "error",
            "location": "plan_generation",
            "failure_code": "spine_missing_phase",
            "failure_reason": issue["message"],
            "details": {"week_index": details.get("week_index")},
        }
    if code == "structure_invalid_long_run":
        return {
            "rule": "spine_structure",
            "severity": "error",
            "location": "plan_generation",
            "failure_code": "spine_invalid_long_run",
            "failure_reason": issue["message"],
            "details": {
                "week_index": details.get("week_index"),
                "long_run_miles": details.get("long_run_miles"),
            },
        }
    if code == "peak_not_reached_max_below_target":
        return {
            "rule": "spine_peak_not_reached",
            "severity": "error",
            "location": "plan_generation",
            "failure_code": "spine_peak_not_reached",
            "failure_reason": issue["message"],
            "details": {
                "max_long_run_miles": details.get("max_long_run_miles"),
                "adaptive_peak_miles": details.get("adaptive_peak_miles"),
                "min_required_max_long_run_miles": details.get(
                    "min_required_max_long_run_miles"
                ),
            },
        }
    return {
        "rule": code,
        "severity": issue["severity"],
        "location": "plan_generation",
        "failure_code": code,
        "failure_reason": issue["message"],
        "details": details,
    }
