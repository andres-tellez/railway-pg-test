"""
Long-run structural invariants on generated plans.

Uses the same deterministic inputs and patches as ``test_plan_generation_regression``.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from tests.test_plan_generation_regression import (
    REGRESSION_CASES,
    RegressionCase,
    _apply_determinism_patches,
    _run_case,
)

_PEAK_LR_FLOOR_RATIO = 0.85
_FLOAT_TOL = 1e-6


def _weeks(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    assert "draft" in plan, "expected top-level 'draft'"
    draft = plan["draft"]
    assert isinstance(draft, dict)
    assert "weeks" in draft
    wks = draft["weeks"]
    assert isinstance(wks, list)
    return wks


def _taper_start_index(weeks: List[Dict[str, Any]]) -> int:
    for i, w in enumerate(weeks):
        if w.get("phase") == "Taper":
            return i
    return len(weeks)


def _peak_weeks_before_taper(
    weeks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    t0 = _taper_start_index(weeks)
    return [w for i, w in enumerate(weeks) if i < t0 and w.get("phase") == "Peak"]


def _taper_weeks(weeks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [w for w in weeks if w.get("phase") == "Taper"]


def _accumulation_weeks_ordered(weeks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Base + Build weeks in calendar order (cutback long runs often land in Base)."""
    acc = [w for w in weeks if w.get("phase") in ("Base", "Build")]
    return sorted(acc, key=lambda w: int(w.get("week_number") or 0))


@pytest.mark.parametrize(
    "case",
    REGRESSION_CASES,
    ids=[c.case_id for c in REGRESSION_CASES],
)
def test_peak_phase_floor(
    case: RegressionCase,
    test_db_session: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_determinism_patches(monkeypatch, case)
    result = _run_case(test_db_session, case)
    weeks = _weeks(result)
    peak = _peak_weeks_before_taper(weeks)
    assert peak, f"{case.case_id}: expected at least one Peak week before Taper"
    peak_lrs = [float(w.get("long_run_miles") or 0.0) for w in peak]
    peak_lr = max(peak_lrs)
    floor = peak_lr * _PEAK_LR_FLOOR_RATIO - _FLOAT_TOL
    for w, lr in zip(peak, peak_lrs):
        assert lr + _FLOAT_TOL >= floor, (
            f"{case.case_id}: Peak week {w.get('week_number')!r} long_run_miles={lr} "
            f"below peak_lr*0.85 (peak_lr={peak_lr}, floor≈{peak_lr * _PEAK_LR_FLOOR_RATIO})"
        )


@pytest.mark.parametrize(
    "case",
    REGRESSION_CASES,
    ids=[c.case_id for c in REGRESSION_CASES],
)
def test_peak_preserves_variation(
    case: RegressionCase,
    test_db_session: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_determinism_patches(monkeypatch, case)
    result = _run_case(test_db_session, case)
    weeks = _weeks(result)
    peak = _peak_weeks_before_taper(weeks)
    assert len(peak) >= 2, f"{case.case_id}: need multiple Peak weeks for this check"
    peak_lrs = [float(w.get("long_run_miles") or 0.0) for w in peak]
    assert (
        len(set(round(x, 4) for x in peak_lrs)) > 1
    ), f"{case.case_id}: Peak long_run_miles flattened to one value: {peak_lrs!r}"


@pytest.mark.parametrize(
    "case",
    REGRESSION_CASES,
    ids=[c.case_id for c in REGRESSION_CASES],
)
def test_taper_reduces_long_runs(
    case: RegressionCase,
    test_db_session: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_determinism_patches(monkeypatch, case)
    result = _run_case(test_db_session, case)
    weeks = _weeks(result)
    peak = _peak_weeks_before_taper(weeks)
    taper = _taper_weeks(weeks)
    assert peak, f"{case.case_id}: expected Peak weeks"
    assert taper, f"{case.case_id}: expected Taper weeks"
    peak_sorted = sorted(peak, key=lambda w: int(w.get("week_number") or 0))
    last_peak_lr = float(peak_sorted[-1].get("long_run_miles") or 0.0)
    assert any(
        float(w.get("long_run_miles") or 0.0) + _FLOAT_TOL < last_peak_lr for w in taper
    ), (
        f"{case.case_id}: expected some Taper long_run below last Peak "
        f"(last_peak_lr={last_peak_lr}, taper={[float(w.get('long_run_miles')) for w in taper]})"
    )


@pytest.mark.parametrize(
    "case",
    REGRESSION_CASES,
    ids=[c.case_id for c in REGRESSION_CASES],
)
def test_build_has_cutbacks(
    case: RegressionCase,
    test_db_session: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_determinism_patches(monkeypatch, case)
    result = _run_case(test_db_session, case)
    weeks = _weeks(result)
    acc_ordered = _accumulation_weeks_ordered(weeks)
    assert len(acc_ordered) >= 2, f"{case.case_id}: need multiple Base/Build weeks"
    lr = [float(w.get("long_run_miles") or 0.0) for w in acc_ordered]
    assert any(
        lr[i] + _FLOAT_TOL < lr[i - 1] for i in range(1, len(lr))
    ), f"{case.case_id}: Base/Build long_run_miles never decrease week-over-week: {lr!r}"
