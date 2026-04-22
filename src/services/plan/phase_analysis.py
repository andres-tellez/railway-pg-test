"""
Canonical builder for the V1.6 §8 **phase analysis** payload.

Single source of truth (PHASE_3_IMPLEMENTATION_CHECKLIST §X.5) for the
LLM agent tool ``get_phase_analysis`` (V1.6 Phase B 3B.6,
AGENTIC_COACH Topic 9).

Scope
-----
For a single training phase (Base / Build / Peak / Taper), surface the
**per-run-type KPI trend for phase-to-date** so the coach can answer
questions like:

* "How is my Base phase going?"
* "Is my Tempo zone compliance improving through Build?"
* "How did I execute my Long runs so far in Peak?"

A "phase week" is any plan week whose resolved phase (per
:func:`src.services.phase.phase_priority.resolve_week_phase` majority-
of-days / plurality rule with later-phase tie-break) equals the
requested phase. A phase therefore owns an integer number of plan
weeks; transition weeks are assigned to the phase that wins the
majority, identical to ``get_weekly_plan`` and ``get_plan_overview``.

"Phase-to-date" = phase weeks whose Monday is on or before today.
Future phase weeks are counted for context (``phase_weeks.future``)
but contribute **no** execution data to the per-run-type trend — this
structurally extends the §19.5 future-week "no actuals" rule to any
phase-week that hasn't started yet.

Per-run-type KPI coverage (V1.6)
--------------------------------
V1.6 exposes the **canonical actual.\\* block** KPIs per run type:

* ``zone_compliance_pct`` (§7 core KPI, all types) — weekly average +
  chronological trend series + aggregate mean.
* ``completion_miles_pct`` (§7 supporting adherence metric) — per-run
  (``actual_miles / planned_miles``) averaged across the phase-to-date
  runs of each type.
* ``deviation_direction`` (§5 Phase A item 3) — distribution of
  ``too_hard`` / ``too_easy`` / ``on_target`` / ``null`` outcomes
  across the phase-to-date runs of each type.
* ``run_score`` — distribution of 🟢 / 🟡 / 🔴 outcomes (from
  :attr:`src.db.models.activities.Activity.run_score`).

Full KPI coverage (HR Drift / Aerobic Efficiency / Pace Consistency)
is **deferred** to V1.7 because their canonical per-activity producer
does not yet live on the ``actual.*`` namespace for every run type —
today those metrics are only available through ``v_easy_runs`` which
is Easy-only. Emitting them here would violate the §X.5 single-
source-of-truth rule ("every deterministic field has exactly one
producer"). When a canonical per-activity HR-drift producer lands, it
plugs into the same ``by_run_type`` shape additively.

Future / empty phase contract
-----------------------------
The tool never errors on "phase not yet started":

* If the requested phase has zero weeks in the active plan (e.g.
  athlete asks about ``"Taper"`` of a 12-week Base-only block), the
  payload carries ``phase_weeks.total = 0`` and ``by_run_type = {}``
  but still attaches ``phase_kpi_priority`` so the coach can
  explain the intent of that phase without executing runs.
* If every phase week is still in the future, ``phase_weeks.completed
  = 0`` and ``by_run_type`` is empty — the coach narrates planned
  emphasis only.
* Invalid ``phase_id`` (not one of the four canonical strings, case-
  insensitive) returns ``{"error": "invalid_phase", ...}``.
* No plan on file returns ``{"error": "no_plan", ...}`` so callers
  (HTTP wrapper and the LLM tool) translate to their own envelopes.

Derivation policy
-----------------
Every deterministic field is produced by a canonical module — this
service composes, it never recomputes:

* Phase resolution per week —
  :func:`src.services.phase.phase_priority.resolve_week_phase`.
* §8 emphasis list —
  :func:`src.services.phase.phase_priority.phase_kpi_priority_for_phase`.
* Per-activity ``actual.*`` fields —
  :func:`src.smartcoach_mobile_coach.run_insight.build_run_execution_block`.
* Canonical ``run_type_key`` —
  :func:`src.services.plan.weekly_plan.resolve_plan_workout_run_type_key`.
* Week bounds —
  :func:`src.utils.date_helpers.get_week_bounds_for_date`.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.services.phase.phase_priority import (
    Phase,
    phase_kpi_priority_for_phase,
    resolve_week_phase,
)
from src.services.phase.weekly_progress import (
    PriorityKpiDeviation,
    WeeklyPhaseProgress,
    compute_weekly_phase_progress,
)
from src.services.plan.phase_goal import get_active_phase_goal
from src.services.plan.plan_status import plan_status_for_day
from src.services.plan.weekly_plan import resolve_plan_workout_run_type_key
from src.services.scoring.adherence import (
    WeeklyAdherenceEntry,
    compute_weekly_adherence,
)
from src.services.scoring.deviation import DeviationDirection
from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_percent,
)
from src.smartcoach_mobile_coach.run_insight import build_run_execution_block
from src.utils.date_helpers import get_week_bounds_for_date
from src.utils.run_type_constants import RUN_TYPE_DEFINITIONS
from src.utils.timezone_helpers import get_today_date_in_timezone

logger = logging.getLogger(__name__)


def _normalize_phase_id(raw: Any) -> Optional[Phase]:
    """
    Resolve a case-insensitive ``phase_id`` string to the canonical
    :class:`Phase` enum. Returns ``None`` on any invalid input so the
    caller can emit the standard ``invalid_phase`` envelope.
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return Phase(cleaned.capitalize())
    except ValueError:
        return None


def _load_active_or_most_recent_plan(session: Session, user_id: UUID):
    """
    Mirror of :func:`src.services.plan.weekly_plan._load_active_or_most_recent_plan`
    and :func:`src.services.plan.plan_overview._load_active_or_most_recent_plan`.
    Both plan-read surfaces must agree on "which plan is this?".
    """
    plan_row = (
        session.query(
            Plan.id,
            Plan.plan_name,
            Plan.race_date,
            Plan.race_distance,
            Plan.training_days,
        )
        .filter(Plan.user_id == user_id, Plan.is_active.is_(True))
        .order_by(Plan.created_at.desc())
        .first()
    )
    if plan_row is not None:
        return plan_row
    return (
        session.query(
            Plan.id,
            Plan.plan_name,
            Plan.race_date,
            Plan.race_distance,
            Plan.training_days,
        )
        .filter(Plan.user_id == user_id)
        .order_by(Plan.created_at.desc())
        .first()
    )


def _empty_run_type_bucket() -> Dict[str, Any]:
    """
    Zero-state bucket for a ``by_run_type[key]`` entry.

    Every numeric aggregate is ``None`` (V1.6 §4 null-vs-absent
    convention: "checked, no value"). Distribution counts are zeroed
    so the coach can always read a stable shape without branching
    on key presence.
    """
    return {
        "run_count_planned": 0,
        "run_count_matched": 0,
        "miles_planned_total": 0.0,
        "miles_actual_total": 0.0,
        "zone_compliance_pct": {
            "avg": None,
            "trend": [],
        },
        "completion_miles_pct_avg": None,
        "deviation_direction_distribution": {
            "too_hard": 0,
            "too_easy": 0,
            "on_target": 0,
            "null": 0,
        },
        "run_score_distribution": {
            "green": 0,
            "yellow": 0,
            "red": 0,
            "null": 0,
        },
    }


def _group_plan_weeks(
    workouts: List[PlanWorkout],
) -> Tuple[Dict[date, List[PlanWorkout]], Optional[date], Optional[date]]:
    """
    Group all plan workouts by the Monday anchor of their week.

    Returns ``(by_monday, first_monday, last_monday)``. When the plan
    has zero workouts both boundaries are ``None`` and ``by_monday``
    is empty.
    """
    by_monday: Dict[date, List[PlanWorkout]] = {}
    for w in workouts:
        monday, _sunday = get_week_bounds_for_date(w.date)
        by_monday.setdefault(monday, []).append(w)
    if not by_monday:
        return by_monday, None, None
    return by_monday, min(by_monday.keys()), max(by_monday.keys())


def _select_phase_weeks(
    by_monday: Dict[date, List[PlanWorkout]],
    first_monday: date,
    last_monday: date,
    phase: Phase,
) -> List[Tuple[int, date, List[PlanWorkout]]]:
    """
    Walk the plan week-by-week and return every week whose resolved
    phase equals the requested phase.

    Each element is ``(week_index, week_start, workouts_in_week)``.
    ``week_index`` is 1-based and matches the index ``get_plan_overview``
    would emit, so two surfaces agree on what "week 5" means.
    """
    selected: List[Tuple[int, date, List[PlanWorkout]]] = []
    cursor = first_monday
    week_index = 0
    while cursor <= last_monday:
        week_index += 1
        this_week = by_monday.get(cursor, [])
        resolved = resolve_week_phase(w.phase for w in this_week)
        if resolved is phase:
            selected.append((week_index, cursor, this_week))
        cursor = cursor + timedelta(days=7)
    return selected


def _load_matched_activities(
    session: Session,
    user_id: UUID,
    plan_workout_ids: List[int],
) -> Dict[int, Activity]:
    """
    ``{plan_workout_id: Activity}`` for the most recent activity
    matching each plan workout. Mirrors
    :func:`src.services.plan.weekly_plan._load_matched_activities_by_pw_id`.
    """
    if not plan_workout_ids:
        return {}
    acts = (
        session.query(Activity)
        .filter(
            Activity.matched_plan_workout_id.in_(plan_workout_ids),
            Activity.user_id == user_id,
        )
        .order_by(desc(Activity.start_date))
        .all()
    )
    by_pw: Dict[int, Activity] = {}
    for a in acts:
        mpw = a.matched_plan_workout_id
        if mpw is not None and mpw not in by_pw:
            by_pw[mpw] = a
    return by_pw


def _classify_run_score(score: Any) -> str:
    """
    Canonical green / yellow / red / null bucket for an activity's
    ``run_score`` integer.

    Matches the spec §9 "Green/Yellow/Red" summary score. Spec §9 does
    not pin the integer thresholds (they're produced upstream by the
    scoring service); we treat the stored value as the canonical
    three-band enum when it's a small integer in {0,1,2,3,4} and fall
    back to ``"null"`` otherwise so an unknown score can never silently
    corrupt the distribution.
    """
    if score is None:
        return "null"
    try:
        v = int(score)
    except (TypeError, ValueError):
        return "null"
    if v >= 4:
        return "green"
    if v >= 2:
        return "yellow"
    if v >= 0:
        return "red"
    return "null"


def _update_bucket_with_activity(
    bucket: Dict[str, Any],
    execution_block: Dict[str, Any],
    week_start: date,
    week_zc_accumulator: Dict[date, Dict[str, Any]],
) -> None:
    """
    Fold one matched activity's canonical ``actual.*`` fields into
    the per-run-type bucket + the per-week zone-compliance trend
    accumulator.

    ``execution_block`` MUST be the result of
    :func:`build_run_execution_block` — we never read off ``Activity``
    directly so the §X.5 single-source-of-truth invariant holds.
    """
    actual = execution_block.get("actual") or {}

    bucket["run_count_matched"] += 1

    actual_miles = actual.get("miles")
    if actual_miles is not None:
        try:
            bucket["miles_actual_total"] += float(actual_miles)
        except (TypeError, ValueError):
            pass

    zc = actual.get("zone_compliance_pct")
    if zc is not None:
        try:
            zc_val = float(zc)
            bucket.setdefault("_zc_samples", []).append(zc_val)
            wk = week_zc_accumulator.setdefault(week_start, {"sum": 0.0, "n": 0})
            wk["sum"] += zc_val
            wk["n"] += 1
        except (TypeError, ValueError):
            pass

    cp = actual.get("completion_pct")
    if cp is not None:
        try:
            bucket.setdefault("_cp_samples", []).append(float(cp))
        except (TypeError, ValueError):
            pass

    deviation = actual.get("deviation_direction")
    key = deviation if deviation in ("too_hard", "too_easy", "on_target") else "null"
    bucket["deviation_direction_distribution"][key] += 1

    score_bucket = _classify_run_score(actual.get("run_score"))
    bucket["run_score_distribution"][score_bucket] += 1


def _finalize_bucket(
    bucket: Dict[str, Any],
    week_zc_accumulator: Dict[date, Dict[str, Any]],
) -> None:
    """
    Close out the running aggregates on a per-run-type bucket.

    Emits:
    * ``zone_compliance_pct.avg`` — mean of all per-run samples.
    * ``zone_compliance_pct.trend`` — chronological per-week averages.
    * ``completion_miles_pct_avg`` — mean of all per-run samples.

    Strips the internal ``_*_samples`` scratch keys so the returned
    shape is wire-safe.
    """
    zc_samples: List[float] = bucket.pop("_zc_samples", [])
    cp_samples: List[float] = bucket.pop("_cp_samples", [])

    zc_trend: List[Dict[str, Any]] = []
    for wk_start in sorted(week_zc_accumulator.keys()):
        agg = week_zc_accumulator[wk_start]
        if agg["n"] > 0:
            zc_trend.append(
                {
                    "week_start": wk_start.isoformat(),
                    "avg_zone_compliance_pct": agg["sum"] / agg["n"],
                    "n": agg["n"],
                }
            )

    zc_avg = (sum(zc_samples) / len(zc_samples)) if zc_samples else None
    cp_avg = (sum(cp_samples) / len(cp_samples)) if cp_samples else None
    bucket["zone_compliance_pct"] = {
        "avg": zc_avg,
        "trend": zc_trend,
    }
    bucket["completion_miles_pct_avg"] = cp_avg
    # V1.6 3B.7 — Topic 4 display-ready strings for the per-run-type
    # aggregate. Distances and percentages are pre-formatted so the
    # coach can cite them verbatim ("4 runs, 32.00 mi, 78 % ZC") in
    # phase-level narratives without doing math on the fly. Numeric
    # fields remain the single source of truth for any comparisons.
    bucket["display"] = {
        "miles_planned_total": format_distance_mi(
            bucket.get("miles_planned_total") or 0.0
        ),
        "miles_actual_total": format_distance_mi(
            bucket.get("miles_actual_total") or 0.0
        ),
        "zone_compliance_pct_avg": format_percent(zc_avg),
        "completion_miles_pct_avg": format_percent(cp_avg),
    }


def _classify_phase_temporality(
    today: date,
    phase_start: Optional[date],
    phase_end: Optional[date],
) -> str:
    """
    Phase-level temporality based on the phase's first and last
    plan-week Monday.

    * ``"future"`` — phase hasn't started yet (``today < phase_start``).
    * ``"current"`` — today is inside the phase window.
    * ``"past"`` — phase has fully ended (``today > phase_end + 6 days``).
    * ``"empty"`` — phase has no weeks in the plan (boundaries None).
    """
    if phase_start is None or phase_end is None:
        return "empty"
    phase_last_sunday = phase_end + timedelta(days=6)
    if today < phase_start:
        return "future"
    if today > phase_last_sunday:
        return "past"
    return "current"


# --------------------------------------------------------------------- #
# V1.6 Phase D 3D.3 + 3D.7 — goal + weekly progress + rollup
# --------------------------------------------------------------------- #


def _serialize_active_goal(
    session: Session,
    user_id: UUID,
    plan_id: int,
    phase: Phase,
) -> Optional[Dict[str, Any]]:
    """Return a wire-safe ``goal`` sub-payload (or ``None``).

    Reads via :func:`src.services.plan.phase_goal.get_active_phase_goal`
    — the canonical reader — so there is exactly one query shape for
    "the active goal for this phase" across the backend. Kept narrow on
    purpose (no history, no superseded rows) so the LLM payload stays
    small; history can be surfaced in a future iteration via
    ``get_all_goals_for_plan`` when the UX needs it.
    """
    goal = get_active_phase_goal(session, user_id, plan_id, phase)
    if goal is None:
        return None
    return {
        "id": goal.id,
        "goal_text": goal.goal_text,
        "status": goal.status,
        "source": goal.source,
        "confirmed_at": goal.confirmed_at.isoformat() if goal.confirmed_at else None,
        "created_at": goal.created_at.isoformat() if goal.created_at else None,
    }


def _compute_week_progress_entry(
    *,
    week_index: int,
    week_start: date,
    workouts: List[PlanWorkout],
    matched_by_pw: Dict[int, Activity],
    plan_training_days: Any,
    today: date,
    phase: Phase,
) -> Dict[str, Any]:
    """Compose the per-week entry for ``weekly_progress[]``.

    Delegates every deterministic field to its canonical producer:

    * Adherence band → :func:`compute_weekly_adherence` (§7).
    * Priority-KPI aggregate + status →
      :func:`compute_weekly_phase_progress` (§19.4, 3D.6).
    * Per-run ``deviation_direction`` and canonical ``run_type_key`` →
      :func:`build_run_execution_block` +
      :func:`resolve_plan_workout_run_type_key`.

    This helper recomputes inputs from the same rows the main function
    already loaded — it does NOT re-query. The phase-analysis builder
    feeds it ``matched_by_pw`` so we stay within one DB round-trip for
    the entire phase window.
    """
    week_end = week_start + timedelta(days=6)

    adherence_entries: List[WeeklyAdherenceEntry] = []
    priority_entries: List[PriorityKpiDeviation] = []

    for w in workouts:
        act = matched_by_pw.get(w.id)
        day_status = plan_status_for_day(
            has_planned_workout=True,
            has_matching_activity=act is not None,
            day_date=w.date,
            today=today,
        )
        if day_status is not None:
            adherence_entries.append(
                WeeklyAdherenceEntry(
                    plan_status=day_status,
                    completion_pct=(
                        getattr(act, "completion_pct", None)
                        if act is not None
                        else None
                    ),
                    planned_miles=w.miles,
                    actual_miles=(
                        getattr(act, "actual_miles", None) if act is not None else None
                    ),
                )
            )

        if act is None:
            continue

        run_type_key = resolve_plan_workout_run_type_key(w)
        block = build_run_execution_block(act, plan_training_days=plan_training_days)
        actual = block.get("actual") or {}
        deviation_raw = actual.get("deviation_direction")
        deviation: Optional[DeviationDirection]
        try:
            deviation = (
                DeviationDirection(deviation_raw) if deviation_raw is not None else None
            )
        except ValueError:
            deviation = None
        priority_entries.append(
            PriorityKpiDeviation(run_type_key=run_type_key, deviation=deviation)
        )

    adherence_result = compute_weekly_adherence(adherence_entries)
    progress = compute_weekly_phase_progress(
        phase, adherence_result.band, priority_entries
    )

    return {
        "week_index": week_index,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "status": progress.status.value if progress.status is not None else None,
        "adherence_band": (
            adherence_result.band.value if adherence_result.band is not None else None
        ),
        "adherence_runs_pct": adherence_result.adherence_runs_pct,
        "priority_kpi_execution": (
            progress.aggregate.value if progress.aggregate is not None else None
        ),
        "priority_run_type": progress.priority_run_type,
        "priority_run_count": progress.priority_run_count,
        "total_run_count": progress.total_run_count,
    }


def _build_phase_progress_summary(
    weekly_progress: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Roll up per-week statuses into a phase-to-date summary.

    Counts every ``status`` bucket, exposes ``weeks_evaluated`` (total
    entries surfaced — includes ``None`` status weeks so the coach can
    see that a phase has partial coverage), and picks a
    ``dominant_status`` via a simple plurality vote across classifiable
    weeks. Ties resolve by the priority order ``off_track → close →
    on_track`` so the summary is conservative (a 1-1-1 split never
    tells the athlete they're "on track").

    Returns a zero-shape when ``weekly_progress`` is empty — the coach
    still gets a stable block and can narrate "no evaluable weeks yet".
    """
    counts = {
        WeeklyPhaseProgress.ON_TRACK.value: 0,
        WeeklyPhaseProgress.CLOSE.value: 0,
        WeeklyPhaseProgress.OFF_TRACK.value: 0,
        "null": 0,
    }
    for wk in weekly_progress:
        status = wk.get("status")
        if status in counts:
            counts[status] += 1
        else:
            counts["null"] += 1

    # Priority order biases ties toward the more-urgent status — a
    # phase that is one-week-off, one-week-close, one-week-on MUST
    # NOT narrate as "on_track".
    priority_order = [
        WeeklyPhaseProgress.OFF_TRACK.value,
        WeeklyPhaseProgress.CLOSE.value,
        WeeklyPhaseProgress.ON_TRACK.value,
    ]
    dominant_status: Optional[str] = None
    best_count = 0
    for status in priority_order:
        c = counts[status]
        if c > best_count:
            best_count = c
            dominant_status = status

    return {
        "weeks_evaluated": len(weekly_progress),
        "on_track_count": counts[WeeklyPhaseProgress.ON_TRACK.value],
        "close_count": counts[WeeklyPhaseProgress.CLOSE.value],
        "off_track_count": counts[WeeklyPhaseProgress.OFF_TRACK.value],
        "null_count": counts["null"],
        "dominant_status": dominant_status,
    }


def build_phase_analysis_payload(
    session: Session,
    user_id: UUID,
    phase_id: Any,
    *,
    tz: str = "UTC",
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Build the V1.6 Phase B 3B.6 phase-analysis payload.

    Args:
        session: Active SQLAlchemy session.
        user_id: Internal user UUID (not Auth0 subject).
        phase_id: One of ``"Base"``, ``"Build"``, ``"Peak"``, ``"Taper"``
            (case-insensitive). Any other value → ``invalid_phase``
            error envelope.
        tz: IANA timezone name used to resolve "today" when
            ``today`` is not supplied. Defaults to UTC.
        today: Optional explicit "today" override (tests). Overrides
            ``tz`` when provided.

    Returns:
        Either an error envelope
        (``{"error": "no_plan" | "invalid_phase", ...}``) or the full
        payload (see module docstring for shape).

    V1.6 contracts enforced structurally:
        * Only ``actual.*`` fields from :func:`build_run_execution_block`
          contribute — no direct ``Activity`` reads, no recomputed
          KPIs (§X.5).
        * Future phase-weeks contribute no execution data
          (§19.5 extension).
        * Transition weeks resolve identically to
          ``get_weekly_plan`` / ``get_plan_overview`` (§7).
    """
    tz_norm = tz.strip() if isinstance(tz, str) and tz.strip() else "UTC"
    resolved_today: date = (
        today if today is not None else get_today_date_in_timezone(tz_norm)
    )

    phase = _normalize_phase_id(phase_id)
    if phase is None:
        return {
            "error": "invalid_phase",
            "message": (
                "phase_id must be one of Base, Build, Peak, Taper "
                "(case-insensitive)."
            ),
            "allowed": [p.value for p in Phase],
        }

    plan_row = _load_active_or_most_recent_plan(session, user_id)
    if plan_row is None:
        return {"error": "no_plan", "message": "No plan found"}

    phase_priority_payload = {
        "phase": phase.value,
        "priority": [
            {"kpi_id": e.kpi_id, "label": e.label}
            for e in phase_kpi_priority_for_phase(phase)
        ],
    }

    workouts: List[PlanWorkout] = (
        session.query(PlanWorkout)
        .filter(PlanWorkout.plan_id == plan_row.id)
        .order_by(PlanWorkout.date)
        .all()
    )

    by_monday, first_monday, last_monday = _group_plan_weeks(workouts)

    # V1.6 Phase D 3D.3 — active phase goal reads via the canonical
    # writer/reader surface in :mod:`src.services.plan.phase_goal`.
    # Emitted even in empty / future-only phases so the coach can
    # narrate a user-stated intent before any runs land.
    goal_payload = _serialize_active_goal(session, user_id, plan_row.id, phase)

    empty_progress_summary = _build_phase_progress_summary([])

    if not workouts or first_monday is None or last_monday is None:
        return {
            "plan_id": plan_row.id,
            "plan_name": plan_row.plan_name,
            "race_date": (
                plan_row.race_date.isoformat() if plan_row.race_date else None
            ),
            "race_distance": plan_row.race_distance,
            "phase": phase.value,
            "phase_kpi_priority": phase_priority_payload,
            "phase_weeks": {
                "total": 0,
                "completed": 0,
                "in_progress": 0,
                "future": 0,
                "completion_pct": None,
                "phase_temporality": "empty",
            },
            "phase_window": {
                "start": None,
                "end": None,
                "evaluated_through": None,
            },
            "by_run_type": {},
            "goal": goal_payload,
            "weekly_progress": [],
            "phase_progress_summary": empty_progress_summary,
            "timezone": tz_norm,
            "today": resolved_today.isoformat(),
        }

    phase_weeks = _select_phase_weeks(by_monday, first_monday, last_monday, phase)

    if not phase_weeks:
        return {
            "plan_id": plan_row.id,
            "plan_name": plan_row.plan_name,
            "race_date": (
                plan_row.race_date.isoformat() if plan_row.race_date else None
            ),
            "race_distance": plan_row.race_distance,
            "phase": phase.value,
            "phase_kpi_priority": phase_priority_payload,
            "phase_weeks": {
                "total": 0,
                "completed": 0,
                "in_progress": 0,
                "future": 0,
                "completion_pct": None,
                "phase_temporality": "empty",
            },
            "phase_window": {
                "start": None,
                "end": None,
                "evaluated_through": None,
            },
            "by_run_type": {},
            "goal": goal_payload,
            "weekly_progress": [],
            "phase_progress_summary": empty_progress_summary,
            "timezone": tz_norm,
            "today": resolved_today.isoformat(),
        }

    phase_start = phase_weeks[0][1]
    phase_end = phase_weeks[-1][1]
    phase_temporality = _classify_phase_temporality(
        resolved_today, phase_start, phase_end
    )

    # Split phase weeks into (completed | in-progress | future) buckets
    # based on today, so the payload can report plan-level progress
    # without the coach re-deriving from week Mondays.
    completed_weeks: List[Tuple[int, date, List[PlanWorkout]]] = []
    in_progress_weeks: List[Tuple[int, date, List[PlanWorkout]]] = []
    future_weeks: List[Tuple[int, date, List[PlanWorkout]]] = []
    for idx, start, ws in phase_weeks:
        week_end = start + timedelta(days=6)
        if resolved_today > week_end:
            completed_weeks.append((idx, start, ws))
        elif resolved_today < start:
            future_weeks.append((idx, start, ws))
        else:
            in_progress_weeks.append((idx, start, ws))

    evaluable_weeks = completed_weeks + in_progress_weeks

    # Pre-count planned-side totals per run-type across the ENTIRE
    # phase (past + current + future). The coach narrates "you have 4
    # planned Tempo runs in Build; you've completed 2 so far" — the
    # denominator has to be phase-wide or the "so far" loses meaning.
    by_run_type: Dict[str, Dict[str, Any]] = {}
    for _idx, _ws_start, ws in phase_weeks:
        for w in ws:
            key = resolve_plan_workout_run_type_key(w)
            bucket = by_run_type.setdefault(key, _empty_run_type_bucket())
            bucket["run_count_planned"] += 1
            if w.miles is not None:
                try:
                    bucket["miles_planned_total"] += float(w.miles)
                except (TypeError, ValueError):
                    pass

    # Fold matched activities from past+current weeks only. We build
    # a single query across all candidate plan-workout ids so the
    # service scales to a 16-week phase in one DB round-trip.
    candidate_pw_ids: List[int] = []
    for _idx, _ws_start, ws in evaluable_weeks:
        candidate_pw_ids.extend(w.id for w in ws)

    matched_by_pw = _load_matched_activities(session, user_id, candidate_pw_ids)

    # Per-run-type chronological accumulators for the weekly trend.
    # Nested ``{run_type_key: {week_start: {sum, n}}}`` so each bucket
    # emits its own time series at finalize time.
    zc_accumulators: Dict[str, Dict[date, Dict[str, Any]]] = {}

    plan_training_days = plan_row.training_days
    for _idx, ws_start, ws in evaluable_weeks:
        for w in ws:
            act = matched_by_pw.get(w.id)
            if act is None:
                continue
            key = resolve_plan_workout_run_type_key(w)
            bucket = by_run_type.setdefault(key, _empty_run_type_bucket())
            accumulator = zc_accumulators.setdefault(key, {})
            block = build_run_execution_block(
                act, plan_training_days=plan_training_days
            )
            _update_bucket_with_activity(bucket, block, ws_start, accumulator)

    for key, bucket in by_run_type.items():
        _finalize_bucket(bucket, zc_accumulators.get(key, {}))
        # Attach the canonical run-type display metadata so the coach
        # never has to reach into RUN_TYPE_DEFINITIONS to format a
        # display name. Absent on legacy keys (should not happen —
        # normalize_run_type_key returns a canonical key) but guarded
        # for safety.
        rt_def = RUN_TYPE_DEFINITIONS.get(key)
        if rt_def is not None:
            bucket["run_type"] = {
                "key": rt_def.key,
                "display_name": rt_def.display_name,
                "target_zone_ids": list(rt_def.target_zone_ids),
            }

    # V1.6 Phase D 3D.3 + 3D.7 — per-week progress + rollup across the
    # evaluable phase window. Future phase-weeks contribute no entry so
    # the wire-shape never carries speculative statuses for weeks that
    # haven't started yet (§19.5 extension).
    weekly_progress: List[Dict[str, Any]] = []
    for idx, ws_start, ws in evaluable_weeks:
        weekly_progress.append(
            _compute_week_progress_entry(
                week_index=idx,
                week_start=ws_start,
                workouts=ws,
                matched_by_pw=matched_by_pw,
                plan_training_days=plan_training_days,
                today=resolved_today,
                phase=phase,
            )
        )
    phase_progress_summary = _build_phase_progress_summary(weekly_progress)

    total = len(phase_weeks)
    completed = len(completed_weeks)
    in_progress = len(in_progress_weeks)
    future = len(future_weeks)
    completion_pct = (completed + in_progress) / total if total > 0 else None

    last_evaluable_sunday: Optional[date] = None
    if evaluable_weeks:
        last_evaluable_sunday = min(
            resolved_today, evaluable_weeks[-1][1] + timedelta(days=6)
        )

    return {
        "plan_id": plan_row.id,
        "plan_name": plan_row.plan_name,
        "race_date": (plan_row.race_date.isoformat() if plan_row.race_date else None),
        "race_distance": plan_row.race_distance,
        "phase": phase.value,
        "phase_kpi_priority": phase_priority_payload,
        "phase_weeks": {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "future": future,
            "completion_pct": completion_pct,
            "phase_temporality": phase_temporality,
            # V1.6 3B.7 — display string for the phase progress percentage.
            "display": {
                "completion_pct": format_percent(completion_pct),
            },
        },
        "phase_window": {
            "start": phase_start.isoformat(),
            "end": (phase_end + timedelta(days=6)).isoformat(),
            "evaluated_through": (
                last_evaluable_sunday.isoformat()
                if last_evaluable_sunday is not None
                else None
            ),
        },
        "by_run_type": by_run_type,
        "goal": goal_payload,
        "weekly_progress": weekly_progress,
        "phase_progress_summary": phase_progress_summary,
        "timezone": tz_norm,
        "today": resolved_today.isoformat(),
    }


__all__ = [
    "build_phase_analysis_payload",
]
