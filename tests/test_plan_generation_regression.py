"""
Snapshot regression tests for PlanGenerationOrchestratorV2.

Locks full JSON output for fixed inputs. Regenerate baselines:

    PLAN_REGRESSION_UPDATE=1 pytest tests/test_plan_generation_regression.py -q --no-cov

External data paths (materialized views, pace DB, wall clock) are patched so the
orchestrator + Pass1/3/4/validation run unchanged while inputs stay deterministic.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
import difflib
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.db.models.user_identity import UserIdentity
from src.services.training_plan.v2.plan_generation_orchestrator_v2 import (
    PlanGenerationOrchestratorV2,
)
from src.services.training_plan.v2.race_distance_factory_v2 import (
    get_race_distance_services,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "plan_regression"
UPDATE_BASELINES = os.environ.get("PLAN_REGRESSION_UPDATE") == "1"

REGRESSION_USER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

# Keys removed before compare / baseline save (timestamps / known volatile metadata).
_STRIP_KEYS = frozenset(
    {
        "timestamp",
        "created_at",
        "updated_at",
        "generated_at",
    }
)


def _strip_nondeterministic(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _strip_nondeterministic(v)
            for k, v in obj.items()
            if k not in _STRIP_KEYS
        }
    if isinstance(obj, list):
        return [_strip_nondeterministic(x) for x in obj]
    if isinstance(obj, tuple):
        return [_strip_nondeterministic(x) for x in obj]
    return obj


def _json_default(o: Any) -> Any:
    if isinstance(o, (date,)):
        return o.isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def assert_json_equal(actual: Any, expected: Any) -> None:
    """
    Compare full JSON serialization with sorted keys at every object level.

    Intended form (extended with ``default=`` for dates and diff on failure):

        assert json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)
    """
    a = json.dumps(actual, sort_keys=True, default=_json_default)
    b = json.dumps(expected, sort_keys=True, default=_json_default)
    if a == b:
        return
    diff = "\n".join(
        difflib.unified_diff(
            b.splitlines(),
            a.splitlines(),
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
    )
    raise AssertionError(f"JSON mismatch (sorted keys, json.dumps):\n{diff}")


logger = logging.getLogger(__name__)

# Primary taxonomy from spec; production also emits these aliases (do not warn).
_KNOWN_WORKOUT_TYPES_PRIMARY = frozenset(
    {"easy", "long_run", "tempo", "interval", "recovery"}
)
_KNOWN_WORKOUT_TYPES_ALIASES = frozenset({"intervals", "Race"})

# Pass3/rounding may leave distance_miles vs miles differing by up to ~0.5 mi.
_DISTANCE_TOL = 0.55


def assert_plan_structure(plan: Dict[str, Any]) -> None:
    """Validate minimal shape of the generated plan (draft.weeks[].workouts[])."""
    if "draft" not in plan:
        raise AssertionError("plan_structure: missing top-level key 'draft'")
    draft = plan["draft"]
    if not isinstance(draft, dict):
        raise AssertionError(
            f"plan_structure: 'draft' must be a dict, got {type(draft).__name__}"
        )
    if "weeks" not in draft:
        raise AssertionError("plan_structure: missing 'weeks' inside draft")
    weeks = draft["weeks"]
    if not isinstance(weeks, list):
        raise AssertionError(
            f"plan_structure: draft.weeks must be a list, got {type(weeks).__name__}"
        )
    for wi, week in enumerate(weeks):
        if not isinstance(week, dict):
            raise AssertionError(
                f"plan_structure: week index {wi} must be a dict, got {type(week).__name__}"
            )
        if "week_number" not in week:
            wn = week.get("week_number", "?")
            raise AssertionError(
                f"plan_structure: week index {wi} (week_number={wn!r}) missing 'week_number' key"
            )
        wn = week["week_number"]
        if "workouts" not in week:
            raise AssertionError(
                f"plan_structure: week {wn} (index {wi}) missing 'workouts' key"
            )
        wouts = week["workouts"]
        if not isinstance(wouts, list):
            raise AssertionError(
                f"plan_structure: week {wn} (index {wi}) 'workouts' must be a list, "
                f"got {type(wouts).__name__}"
            )
        for j, wo in enumerate(wouts):
            if not isinstance(wo, dict):
                raise AssertionError(
                    f"plan_structure: week {wn} workout index {j} must be a dict, "
                    f"got {type(wo).__name__}"
                )
            if "type" not in wo:
                raise AssertionError(
                    f"plan_structure: week {wn} workout index {j} (day={wo.get('day')!r}) "
                    f"missing 'type'"
                )
            if "miles" not in wo:
                raise AssertionError(
                    f"plan_structure: week {wn} workout index {j} (day={wo.get('day')!r}, "
                    f"type={wo.get('type')!r}) missing 'miles'"
                )


def assert_consistency(plan: Dict[str, Any]) -> None:
    """
    If both distance fields exist on a workout, they must match within tolerance.

    Uses 0.55 mi tolerance so half-mile rounding differences between fields still pass.
    """
    draft = plan.get("draft") or {}
    weeks = draft.get("weeks") or []
    for wi, week in enumerate(weeks):
        if not isinstance(week, dict):
            continue
        wn = week.get("week_number", wi)
        for j, wo in enumerate(week.get("workouts") or []):
            if not isinstance(wo, dict):
                continue
            if "distance_miles" in wo and "miles" in wo:
                d1 = float(wo["distance_miles"])
                d2 = float(wo["miles"])
                if abs(d1 - d2) >= _DISTANCE_TOL:
                    raise AssertionError(
                        f"consistency: week {wn} workout index {j} (day={wo.get('day')!r}): "
                        f"distance_miles={d1} vs miles={d2} (tol={_DISTANCE_TOL})"
                    )


def assert_invariants(plan: Dict[str, Any]) -> None:
    """
    Cross-field checks on draft weeks/workouts.

    Race Week uses long_run_miles==0 and replaces the long run with a Race workout;
    those weeks are exempt from long-run mileage and long_run-type requirements.
    """
    draft = plan.get("draft") or {}
    weeks = draft.get("weeks") or []
    unknown_types: set[str] = set()

    for wi, week in enumerate(weeks):
        if not isinstance(week, dict):
            continue
        wn = week.get("week_number", wi)
        phase = str(week.get("phase") or "")
        is_race_week = phase.strip().lower() == "race week"

        wouts = week.get("workouts") or []
        if not isinstance(wouts, list):
            raise AssertionError(f"invariants: week {wn}: 'workouts' must be a list")

        types_seen = []
        for j, wo in enumerate(wouts):
            if not isinstance(wo, dict):
                continue
            t = wo.get("type")
            if t is not None:
                types_seen.append(str(t))
            if t is not None:
                ts = str(t)
                if (
                    ts not in _KNOWN_WORKOUT_TYPES_PRIMARY
                    and ts not in _KNOWN_WORKOUT_TYPES_ALIASES
                ):
                    unknown_types.add(ts)

        if is_race_week:
            has_race_or_long = any(
                str(wo.get("type")) in ("long_run", "Race")
                for wo in wouts
                if isinstance(wo, dict)
            )
            if not has_race_or_long:
                raise AssertionError(
                    f"invariants: week {wn} (Race Week): expected at least one workout "
                    f"with type 'long_run' or 'Race'"
                )
        else:
            if not any(str(t) == "long_run" for t in types_seen):
                raise AssertionError(
                    f"invariants: week {wn} (phase={phase!r}): no workout with type=='long_run' "
                    f"(workout types: {types_seen})"
                )

        lr = float(week.get("long_run_miles") or 0)
        if not is_race_week and lr <= 0:
            raise AssertionError(
                f"invariants: week {wn} (phase={phase!r}): long_run_miles must be > 0, got {lr}"
            )

        wm = float(week.get("weekly_mileage") or 0)
        if not is_race_week and wm + 1e-6 < lr:
            raise AssertionError(
                f"invariants: week {wn}: weekly_mileage ({wm}) must be >= long_run_miles ({lr})"
            )

    if unknown_types:
        logger.warning(
            "plan_regression: workout types outside primary allowlist %s (logged only): %s",
            sorted(_KNOWN_WORKOUT_TYPES_PRIMARY),
            sorted(unknown_types),
        )


def _no_consecutive_mv(
    session: Any,
    user_id: str,
    *,
    min_consecutive_weeks: int = 3,
) -> Dict[str, Any]:
    return {
        "has_consecutive_runs": False,
        "consecutive_count": 0,
        "weekly_long_runs": [],
        "longest_recent": 0.0,
        "has_recent_reduction": False,
        "most_recent_long_run": 0.0,
    }


def _fixed_pace_seed(
    *args: Any,
    week1_long: float | None = None,
    lookback_weeks: int | None = None,
    config: Any = None,
    strategies: Any = None,
    **kwargs: Any,
) -> Any:
    from src.smartcoach_mobile_coach.runner_profile.models import (
        PaceZoneBand,
        PaceZoneComputation,
    )

    return PaceZoneComputation(
        pace_z2=PaceZoneBand(low_sec=630, high_sec=690, display="10:30-11:30/mi"),
        pace_z3=PaceZoneBand(low_sec=610, high_sec=625, display="10:10-10:25/mi"),
        pace_z4=PaceZoneBand(low_sec=570, high_sec=580, display="9:30-9:40/mi"),
        pace_source="test",
        pace_computed_at=datetime.now().astimezone(),
        marathon_sec=600,
        week1_long_cap=max(8.0, float(week1_long or 8.0)),
    )


@dataclass(frozen=True)
class RegressionCase:
    case_id: str
    weekly_mileage: float
    longest_run: float
    weekly_long_run_series: List[float]
    recent_3w: float
    plan_request: Dict[str, Any]


def _base_plan_request(**overrides: Any) -> Dict[str, Any]:
    base = {
        "race_distance": "Marathon",
        "primary_goal": "Just Finish",
        "user_timezone": "UTC",
        "training_days": ["Tue", "Thu", "Sat", "Sun"],
    }
    base.update(overrides)
    return base


REGRESSION_CASES: List[RegressionCase] = [
    RegressionCase(
        case_id="case_1",
        weekly_mileage=18.0,
        longest_run=8.0,
        weekly_long_run_series=[8.0, 7.5, 8.0],
        recent_3w=8.0,
        plan_request=_base_plan_request(race_date="2026-10-11"),
    ),
    RegressionCase(
        case_id="case_2",
        weekly_mileage=38.0,
        longest_run=14.0,
        weekly_long_run_series=[14.0, 13.5, 13.0],
        recent_3w=14.0,
        plan_request=_base_plan_request(race_date="2026-10-11"),
    ),
    RegressionCase(
        case_id="case_3",
        weekly_mileage=58.0,
        longest_run=20.0,
        weekly_long_run_series=[20.0, 19.0, 18.5],
        recent_3w=20.0,
        plan_request=_base_plan_request(race_date="2026-10-11"),
    ),
    RegressionCase(
        case_id="case_4",
        weekly_mileage=48.0,
        longest_run=16.0,
        weekly_long_run_series=[16.0, 15.5, 15.0],
        recent_3w=16.0,
        plan_request=_base_plan_request(
            race_date="2026-03-22",
        ),
    ),
    RegressionCase(
        case_id="case_5",
        weekly_mileage=12.0,
        longest_run=6.0,
        weekly_long_run_series=[6.0, 6.0],
        recent_3w=6.0,
        plan_request=_base_plan_request(race_date="2026-10-11"),
    ),
]


def _apply_determinism_patches(
    monkeypatch: pytest.MonkeyPatch,
    case: RegressionCase,
) -> None:
    _fit = (case.weekly_mileage, case.longest_run)

    def _fake_fitness(session, user_id, athlete_id=None):
        return _fit

    # Patch where the orchestrator looks up the name (import-bound reference).
    monkeypatch.setattr(
        "src.services.training_plan.v2.plan_generation_orchestrator_v2.get_weekly_fitness_from_materialized_view",
        _fake_fitness,
    )

    from src.services.training_plan.v2.marathon import pass1_longrun_first_v2 as p1

    series = list(case.weekly_long_run_series)

    monkeypatch.setattr(
        p1,
        "detect_consecutive_long_runs_from_materialized_view",
        _no_consecutive_mv,
    )
    monkeypatch.setattr(
        p1,
        "fetch_recent_weekly_long_run_distances",
        lambda session, user_id, max_weeks=6: list(series[:max_weeks]),
    )
    monkeypatch.setattr(
        p1,
        "recent_longest_3w_from_materialized_view",
        lambda session, user_id, days=21: float(case.recent_3w),
    )

    monkeypatch.setattr(
        "src.utils.timezone_helpers.get_today_date_in_timezone",
        lambda tz: date(2026, 1, 5),
    )

    monkeypatch.setattr(
        "src.services.training_plan.v2.plan_generation_orchestrator_v2.get_runner_pace_zones_for_plan_generation",
        lambda *args, **kwargs: _fixed_pace_seed(*args, **kwargs),
    )


def _run_case(test_db_session: Any, case: RegressionCase) -> Dict[str, Any]:
    test_db_session.add(
        UserIdentity(user_id=REGRESSION_USER_ID, name="Regression Runner")
    )
    test_db_session.flush()

    services = get_race_distance_services(
        case.plan_request.get("race_distance", "Marathon")
    )
    orchestrator = PlanGenerationOrchestratorV2(
        config=services["race_config"],
        race_type=services["race_type"],
        scenario=None,
    )
    runner_ctx: Dict[str, Any] = {
        "session": test_db_session,
        "user_id": str(REGRESSION_USER_ID),
        "plan_request": deepcopy(case.plan_request),
        "training_days": case.plan_request.get("training_days"),
        "unit_system": "imperial",
    }
    return orchestrator.generate_longrun_first(runner_ctx, mode="rolling", week_logs={})


def _roundtrip_json(data: Any) -> Any:
    """Baseline file round-trip so types match (e.g. int vs float where JSON differs)."""
    s = json.dumps(data, sort_keys=True, default=_json_default)
    return json.loads(s)


@pytest.mark.parametrize(
    "case",
    REGRESSION_CASES,
    ids=[c.case_id for c in REGRESSION_CASES],
)
def test_plan_generation_regression_snapshot(
    case: RegressionCase,
    test_db_session: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_determinism_patches(monkeypatch, case)
    actual = _run_case(test_db_session, case)
    actual_clean = _strip_nondeterministic(actual)

    path = FIXTURE_DIR / f"{case.case_id}.json"
    if UPDATE_BASELINES:
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(actual_clean, indent=2, sort_keys=True, default=_json_default)
            + "\n",
            encoding="utf-8",
        )
        pytest.skip(f"Wrote baseline {path}")

    if not path.is_file():
        pytest.fail(
            f"Missing baseline {path}. Generate with:\n"
            f"  PLAN_REGRESSION_UPDATE=1 pytest {__file__} -k {case.case_id} -q --no-cov"
        )

    expected = _roundtrip_json(json.loads(path.read_text(encoding="utf-8")))
    assert_json_equal(actual_clean, expected)

    assert_plan_structure(actual)
    assert_consistency(actual)
    assert_invariants(actual)
