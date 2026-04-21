"""
Canonical producer for V1.6 §7 weekly adherence metrics.

PHASE_3_IMPLEMENTATION_CHECKLIST §X.5 single-source-of-truth: this
module is the ONLY place in the codebase that computes
``adherence_runs_pct`` (primary), the ``completion_miles_pct`` weekly
aggregate (supporting), and the Low/Medium/High adherence band used
by §19.8 coach tone and §16 weekly adaptation. All coach payloads,
Phase B plan-aware tools (``get_weekly_plan``, ``get_plan_overview``,
``get_phase_analysis``), and any future adaptation pass MUST consume
these helpers — never inline the ``completed / planned`` ratio nor
the 70 / 90 band thresholds at call sites, never mirror them on
mobile (V1.6 §19: LLM / client must not derive deterministic fields).

The per-run inputs (``completion_pct`` and the 50 % completed-run
threshold) are owned by :mod:`src.services.scoring.completion` and
imported here; this module composes the weekly signal, it does NOT
redefine the per-run contract.

Spec reference (SMARTCOACH_SYSTEM_SPEC_V1.md §7)
-------------------------------------------------
    adherence_runs_pct = completed_runs / planned_runs  (weekly, primary)
    completion_miles_pct (per run)   = actual_miles / planned_miles
    completion_miles_pct (weekly)    = sum(actual_miles_on_planned)
                                       / sum(planned_miles)

Completion rule (per run, from :mod:`completion`):
    A run counts as "completed" iff it has a matched activity whose
    ``completion_pct`` is at least
    :data:`COMPLETION_THRESHOLD_PCT` (50.0). Runs below the threshold
    count as MISSED for adherence purposes regardless of ``plan_status``
    — a 2-mile attempt on a planned 10-mile Long Run does **not**
    count as having done the Long Run.

Unplanned-run exclusion (§7 "Unplanned Runs and Adherence"):
    Entries with ``plan_status == UNPLANNED`` are excluded from both
    the numerator AND the denominator. Extra/unplanned runs are
    tracked separately (see §19.6 for coaching implications); they
    neither inflate nor depress the week's adherence signal.

Bands (§7 "Weekly Adherence Bands"):
    Low    — ``< 70 %``       → §16: reduce load, prioritize consistency
    Medium — ``70 % – 90 %``  → §16: maintain load, hold structure
    High   — ``> 90 %``       → §16: safe to progress within caps

    The spec wording ``70 % – 90 %`` includes both endpoints (closed
    interval). The High band starts strictly above 90 %. A week with
    adherence of exactly 90.0 % is Medium, not High.

Numerator: what counts as a completed run
-----------------------------------------
A planned workout entry counts toward ``completed_runs`` iff all of:

    1. The entry has a matched activity (``plan_status`` is
       :attr:`~PlanStatus.EXECUTED` or :attr:`~PlanStatus.IN_PROGRESS`
       — both carry ``matched_plan_workout_id``). ``PLANNED_ONLY``,
       ``MISSED``, and ``UNPLANNED`` can never be in the numerator.
    2. ``is_run_completed(completion_pct)`` is true (≥ 50 %).

``IN_PROGRESS`` is deliberately eligible: a runner who has completed
today's run at ≥ 50 % *has* completed it for adherence purposes,
even though the day itself is not yet closed. This gives callers a
faithful "so-far" snapshot for in-flight weeks. Downstream adaptation
logic (§16) runs on the closed-week snapshot where IN_PROGRESS
entries have rolled over to EXECUTED, so the semantics converge.

Denominator: what counts as a planned run
-----------------------------------------
Any planned-workout entry (``plan_status ∈ {PLANNED_ONLY,
IN_PROGRESS, EXECUTED, MISSED}``) counts toward ``planned_runs``.
``UNPLANNED`` is excluded per §7.

Empty-week contract
-------------------
A week with zero planned runs returns ``adherence_runs_pct = None``
and ``band = None`` — there is no plan to adhere to and the spec's
ratio is undefined by division-by-zero. ``None`` (V1.6 §4 null-vs-
absent convention) means "checked, no value" so the coach can
distinguish from "not looked at".

Derivation policy — on-read, not persisted
------------------------------------------
Like ``plan_status``, ``baseline_status``, and ``deviation_direction``,
weekly adherence is **derived on read** from the per-day entries. A
persisted ``weekly_adherence_snapshot`` table is a deliberate
non-goal for V1.6 — invalidation on every matched-activity write is
more complex than recomputing from a handful of rows, and the
numbers themselves are trivially fast to aggregate.

Storage/payload contract
------------------------
All percent values are in **percent scale (0-100)** — the same scale
as stored ``completion_pct`` on ``activities`` — so the coach / UI
never has to rescale. ``None`` means undefined (empty week or missing
miles). Callers format for display (no rounding here; see §X.5 split
between computation and presentation).
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, NamedTuple, Optional

from src.services.plan.plan_status import PlanStatus
from src.services.scoring.completion import (
    COMPLETION_THRESHOLD_PCT,
    is_run_completed,
)


class AdherenceBand(str, Enum):
    """V1.6 §7 three-band classification. ``str`` base for JSON ease."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# §7 thresholds. Exposed as named constants so no caller re-inlines them
# and so tests assert against the contract, not a literal.
ADHERENCE_LOW_MAX_EXCLUSIVE_PCT: float = 70.0
"""Below this (strict) → Low band."""

ADHERENCE_HIGH_MIN_EXCLUSIVE_PCT: float = 90.0
"""Above this (strict) → High band. Exactly 90.0 stays Medium."""


class WeeklyAdherenceEntry(NamedTuple):
    """
    One per-day adherence input row.

    Produced by callers at the route / tool boundary from the
    ``(PlanWorkout, Activity)`` pair for each day in the week. The
    aggregator is deliberately shape-agnostic so integration tests
    can assert the math without instantiating ORM rows.

    Fields
    ------
    plan_status
        The V1.6 §6 status for this pairing (from
        :func:`src.services.plan.plan_status.plan_status_for_day` or
        :func:`plan_status_for_activity`). ``UNPLANNED`` entries are
        excluded from both numerator and denominator per §7.
    completion_pct
        The stored per-activity completion percent (0-100 scale) for
        the pairing's matched activity, or ``None`` when there is no
        matched activity / planned miles are undefined.
        Source: ``activities.completion_pct`` as produced by
        :func:`src.services.scoring.completion.compute_completion_pct`.
    planned_miles
        ``plan_workouts.miles`` for the entry, or ``None`` for
        UNPLANNED entries. Used for the weekly
        ``completion_miles_pct`` aggregate.
    actual_miles
        ``activities.actual_miles`` (or the equivalent mileage field
        already normalized by the run-execution-analysis service).
        ``None`` when there is no matched activity. Only contributes
        to the weekly miles aggregate when the entry has a matched
        activity (EXECUTED / IN_PROGRESS).
    """

    plan_status: PlanStatus
    completion_pct: Optional[float] = None
    planned_miles: Optional[float] = None
    actual_miles: Optional[float] = None


class WeeklyAdherenceResult(NamedTuple):
    """
    Output of :func:`compute_weekly_adherence`.

    Percent values are unrounded (see module docstring). All fields
    are safe to emit on the wire — they are primitives or the
    :class:`AdherenceBand` string enum.
    """

    adherence_runs_pct: Optional[float]
    completed_runs: int
    planned_runs: int
    band: Optional[AdherenceBand]
    completion_miles_pct_weekly: Optional[float]
    planned_miles_total: float
    actual_miles_matched_total: float


def classify_adherence_band(pct: Optional[float]) -> Optional[AdherenceBand]:
    """
    Pure classifier for the V1.6 §7 Low / Medium / High bands.

    Returns ``None`` for ``None`` input so callers with an empty week
    (``planned_runs == 0``) can round-trip a ``None`` adherence_pct
    straight to a ``None`` band without a second branch. Negative or
    >100 inputs are accepted — the band semantics clamp naturally
    (``<70`` → Low, ``>90`` → High).

    The boundary semantics mirror the spec wording::

        pct < 70        → LOW
        70 <= pct <= 90 → MEDIUM
        pct > 90        → HIGH

    Exactly 70.0 is Medium (not Low); exactly 90.0 is Medium (not
    High). Tests lock both endpoints.
    """
    if pct is None:
        return None
    value = float(pct)
    if value < ADHERENCE_LOW_MAX_EXCLUSIVE_PCT:
        return AdherenceBand.LOW
    if value > ADHERENCE_HIGH_MIN_EXCLUSIVE_PCT:
        return AdherenceBand.HIGH
    return AdherenceBand.MEDIUM


def compute_weekly_adherence(
    entries: Iterable[WeeklyAdherenceEntry],
) -> WeeklyAdherenceResult:
    """
    Canonical V1.6 §7 weekly adherence aggregator.

    Consumes one :class:`WeeklyAdherenceEntry` per day in the week
    (or per planned-workout; a week with N planned workouts produces
    N entries; UNPLANNED activity entries may optionally be included
    and will be skipped). Returns the composite
    :class:`WeeklyAdherenceResult`.

    Computation (see module docstring for full spec mapping):

        planned_runs       = count of entries where plan_status is
                             PLANNED_ONLY, IN_PROGRESS, EXECUTED, or
                             MISSED
        completed_runs     = count of entries where plan_status is
                             EXECUTED or IN_PROGRESS AND
                             is_run_completed(completion_pct)
        adherence_runs_pct = None if planned_runs == 0 else
                             completed_runs / planned_runs * 100
        band               = classify_adherence_band(adherence_runs_pct)

    Weekly completion-miles aggregate:

        planned_miles_total           = sum of planned_miles across
                                        all planned-workout entries
                                        (UNPLANNED excluded)
        actual_miles_matched_total    = sum of actual_miles across
                                        EXECUTED / IN_PROGRESS entries
                                        that contributed to a matched
                                        activity
        completion_miles_pct_weekly   = None if planned_miles_total
                                        <= 0 else
                                        actual_miles_matched_total /
                                        planned_miles_total * 100

    Miles aggregate uses planned-total (not matched-planned-total) in
    the denominator so a week that drops a long run correctly reports
    lower weekly mileage completion. This matches the spec's
    "supporting metric" framing — it tracks weekly plan-volume
    completion, not per-matched-run shortfall.
    """
    completed_runs = 0
    planned_runs = 0
    planned_miles_total = 0.0
    actual_miles_total = 0.0

    for entry in entries:
        # §7 unplanned-run exclusion — neither side of the ratio,
        # neither side of the miles aggregate.
        if entry.plan_status == PlanStatus.UNPLANNED:
            continue

        planned_runs += 1
        if entry.planned_miles is not None and entry.planned_miles > 0:
            planned_miles_total += float(entry.planned_miles)

        has_matched_activity = entry.plan_status in (
            PlanStatus.EXECUTED,
            PlanStatus.IN_PROGRESS,
        )
        if has_matched_activity:
            if entry.actual_miles is not None and entry.actual_miles > 0:
                actual_miles_total += float(entry.actual_miles)
            # Completed-run gate: must have a matched activity AND
            # meet the §7 50% completion threshold. Matching without
            # hitting the threshold counts as MISSED for adherence.
            if is_run_completed(entry.completion_pct):
                completed_runs += 1

    if planned_runs == 0:
        adherence_pct: Optional[float] = None
    else:
        adherence_pct = (completed_runs / planned_runs) * 100.0

    if planned_miles_total <= 0:
        completion_miles_pct_weekly: Optional[float] = None
    else:
        completion_miles_pct_weekly = (actual_miles_total / planned_miles_total) * 100.0

    return WeeklyAdherenceResult(
        adherence_runs_pct=adherence_pct,
        completed_runs=completed_runs,
        planned_runs=planned_runs,
        band=classify_adherence_band(adherence_pct),
        completion_miles_pct_weekly=completion_miles_pct_weekly,
        planned_miles_total=planned_miles_total,
        actual_miles_matched_total=actual_miles_total,
    )


__all__ = [
    "ADHERENCE_LOW_MAX_EXCLUSIVE_PCT",
    "ADHERENCE_HIGH_MIN_EXCLUSIVE_PCT",
    "AdherenceBand",
    "WeeklyAdherenceEntry",
    "WeeklyAdherenceResult",
    "classify_adherence_band",
    "compute_weekly_adherence",
    # Re-exported so callers that need to reason about the per-run
    # completion threshold don't have to import two modules.
    "COMPLETION_THRESHOLD_PCT",
    "is_run_completed",
]
