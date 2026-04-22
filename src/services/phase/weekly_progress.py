"""
Canonical producer for V1.6 Phase D §19.4 weekly phase-progress status.

PHASE_3_IMPLEMENTATION_CHECKLIST 3D.6 single-source-of-truth: this
module is the ONLY place in the codebase that classifies a week's
progress toward its active phase goal as ``on_track`` / ``close`` /
``off_track`` (or ``None`` for "not classifiable"). All coach payloads,
the Phase D ``get_phase_analysis`` payload extension (3D.3/3D.7), the
phase UX prompt contract (3D.8), and the retrospective helper (3D.4)
MUST consume the helpers below — never reimplement the matrix, never
mirror it on mobile, and never let the LLM override it (V1.6 §19:
LLM must not derive deterministic fields).

Rule (user-locked 2026-04-21, Phase D final decision)
-----------------------------------------------------
Inputs (composed from existing producers — no new KPIs):

* **Adherence band** from
  :func:`src.services.scoring.adherence.classify_adherence_band` —
  Low < 70 %, Medium 70–90 %, High > 90 %.
* **Priority-KPI execution aggregate** across the runs that match the
  **top entry** in the phase's ``phase_kpi_priority`` list. In V1.6 the
  top entry maps to exactly one run type per phase:

      Base  → Easy   (HR Drift / Aerobic Efficiency on easy runs)
      Build → Tempo  (Pace Consistency on Tempo runs)
      Peak  → Long   (Execution across Tempo + Long — Long as the
                     single dominant surface for V1.6)
      Taper → Long   (Maintenance — keep Long execution steady)

  Three buckets derived from each run's ``deviation_direction``:

      mostly_on_target — >= 60 % of priority runs are ``on_target``
      mostly_off       — >= 50 % are ``too_hard`` OR ``too_easy``
                         (union — these are both "off" outcomes)
      mixed            — anything in between

Status matrix:

    High  + mostly_on_target  → on_track
    High  + mixed             → on_track
    High  + mostly_off        → close
    Medium + mostly_on_target → close
    Medium + mixed            → close
    Medium + mostly_off       → off_track
    Low   + any               → off_track

Rationale (from locked spec):

* Adherence dominates — if you didn't run, you can't progress.
* Execution quality is the tie-breaker within adherence.
* Low adherence is always off_track, regardless of execution quality —
  can't hide a missed week behind a couple of great runs.

Edge cases handled deterministically:

* **No runs this week** (empty iterable) → status = ``None``
  ("nothing to classify", NOT a failure state).
* **Future week** → callers MUST pass ``None`` for both ``band`` and
  ``aggregate`` so the status comes out ``None`` — structurally
  consistent with the §19.5 future-week "no actuals" contract.
* **No priority-type runs this week** (e.g. Build phase but user
  skipped all Tempos) → the aggregate helper falls back to the
  full set of completed runs so the week can still be classified.
  If even the full set is empty, aggregate is ``None`` → status
  ``None``.
* **Adherence band is None** (zero planned runs) → status = ``None``;
  there is nothing to be "on track with" when the week has no plan.

Derivation policy — on-read, not persisted
------------------------------------------
Status is derived every time a week is inspected from the band +
aggregate inputs, neither of which is persisted. A persisted
``weekly_progress_snapshot`` is a deliberate non-goal for V1.6 for the
same invalidation reasons as :mod:`adherence`: the numbers change
every time a plan workout is rematched and the inputs are trivial to
aggregate.

Coach-facing contract (§19.4)
-----------------------------
The coach receives the status enum as a **read-only** field and may
render it in natural, varied language ("you're on pace this week" /
"tracking a bit behind" / "this week slipped"), but the validator
(§3C.8 / 3C.9) flags any response that contradicts the stored value.
The LLM must not compute or flip the label.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, List, NamedTuple, Optional

from src.services.phase.phase_priority import Phase
from src.services.scoring.adherence import AdherenceBand
from src.services.scoring.deviation import DeviationDirection
from src.utils.run_type_constants import (
    RUN_TYPE_EASY,
    RUN_TYPE_LONG,
    RUN_TYPE_TEMPO,
)


# --------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------- #


class PriorityKpiExecution(str, Enum):
    """Three-bucket aggregate of the priority run type's deviations.

    Kept distinct from :class:`DeviationDirection` (per-run) so a
    caller can tell "this week's priority-KPI rollup" apart from
    "this single run's outcome" at a glance. ``str`` base for JSON.
    """

    MOSTLY_ON_TARGET = "mostly_on_target"
    MIXED = "mixed"
    MOSTLY_OFF = "mostly_off"


class WeeklyPhaseProgress(str, Enum):
    """V1.6 §19.4 three-value weekly status. ``str`` base for JSON."""

    ON_TRACK = "on_track"
    CLOSE = "close"
    OFF_TRACK = "off_track"


# --------------------------------------------------------------------- #
# Thresholds (spec-locked — callers MUST NOT re-inline these numbers)
# --------------------------------------------------------------------- #

# Locked 2026-04-21: "mostly_on_target = >= 60 %".
MOSTLY_ON_TARGET_MIN_FRACTION: float = 0.60

# Locked 2026-04-21: "mostly_off = >= 50 % too_hard OR too_easy".
MOSTLY_OFF_MIN_FRACTION: float = 0.50


# --------------------------------------------------------------------- #
# Phase → priority run type mapping (V1.6 top entry of §8 emphasis)
# --------------------------------------------------------------------- #

# Implied priority run type for each phase's top §8 emphasis KPI.
# Base → HR Drift / Aerobic Efficiency → Easy runs.
# Build → Pace Consistency (Tempo) → Tempo runs.
# Peak → Execution (Tempo + Long) — Long picked as the single
#   dominant surface for V1.6 (Tempo main-block metrics aren't yet
#   available per :mod:`deviation` module docstring).
# Taper → Maintenance / Recovery signals — Long kept as the surface
#   so one metric story carries through Peak → Taper.
PHASE_PRIORITY_RUN_TYPE: dict[Phase, str] = {
    Phase.BASE: RUN_TYPE_EASY,
    Phase.BUILD: RUN_TYPE_TEMPO,
    Phase.PEAK: RUN_TYPE_LONG,
    Phase.TAPER: RUN_TYPE_LONG,
}


def priority_run_type_for_phase(phase: Phase) -> str:
    """Pure lookup: the V1.6 priority run type for ``phase``.

    Exposed so phase-analysis and coach-prompt callers can resolve the
    run type without re-deriving the mapping. Unknown phases raise
    ``KeyError`` — all four phases are covered in V1.6.
    """
    return PHASE_PRIORITY_RUN_TYPE[phase]


# --------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------- #


class PriorityKpiDeviation(NamedTuple):
    """One per-run input row for the priority-KPI aggregator.

    Fields
    ------
    run_type_key
        Canonical :mod:`src.utils.run_type_constants` key for the
        *executed* run type (lower-case e.g. ``"easy"``, ``"tempo"``,
        ``"long"``). Used to filter for the phase's priority run type.
    deviation
        The run's :class:`DeviationDirection`, or ``None`` when the
        activity was too short / Steady / HR stream missing (see
        spec §5 omission rules).
    """

    run_type_key: str
    deviation: Optional[DeviationDirection]


# --------------------------------------------------------------------- #
# Aggregators
# --------------------------------------------------------------------- #


def classify_priority_kpi_execution(
    deviations: Iterable[Optional[DeviationDirection]],
) -> Optional[PriorityKpiExecution]:
    """Pure aggregator: list of per-run deviations → three-bucket label.

    ``None`` entries are dropped before the ratio is computed — they
    represent "not classifiable" runs (spec §5) and should neither
    inflate ``on_target`` nor ``off`` counts. The result is ``None``
    iff the filtered list is empty.

    Ordering and bucket-derivation precedence (important for edge
    overlaps at exactly 0.60 on_target + exactly 0.50 off):

        * If ``on_target_fraction >= 0.60`` → MOSTLY_ON_TARGET.
          The ``>= 60 %`` spec wording means this branch wins any
          overlap with the MOSTLY_OFF branch — a run list that is
          literally all ``on_target`` cannot also be "mostly off"
          just because 0 % off ≥ 50 %? (it isn't.) Overlap becomes
          real only at contrived splits like 3 ``on_target`` + 3
          ``too_hard`` (50 % / 50 %) → MOSTLY_OFF (off reaches
          threshold, on does not at 0.50 < 0.60).
        * Else if ``off_fraction >= 0.50`` → MOSTLY_OFF.
        * Else → MIXED.
    """
    filtered: List[DeviationDirection] = [d for d in deviations if d is not None]
    n = len(filtered)
    if n == 0:
        return None

    on_target = sum(1 for d in filtered if d == DeviationDirection.ON_TARGET)
    off = sum(
        1
        for d in filtered
        if d in (DeviationDirection.TOO_HARD, DeviationDirection.TOO_EASY)
    )

    on_target_fraction = on_target / n
    off_fraction = off / n

    if on_target_fraction >= MOSTLY_ON_TARGET_MIN_FRACTION:
        return PriorityKpiExecution.MOSTLY_ON_TARGET
    if off_fraction >= MOSTLY_OFF_MIN_FRACTION:
        return PriorityKpiExecution.MOSTLY_OFF
    return PriorityKpiExecution.MIXED


def aggregate_priority_kpi_for_phase(
    phase: Optional[Phase],
    entries: Iterable[PriorityKpiDeviation],
) -> Optional[PriorityKpiExecution]:
    """Compose priority-run filtering + aggregation for a phase.

    Resolution policy (spec-locked):

    1. Filter ``entries`` to the phase's priority run type
       (:func:`priority_run_type_for_phase`).
    2. If that filtered list has at least one non-``None`` deviation,
       classify off it.
    3. Otherwise fall back to the **full** list of ``entries``'
       deviations (per the 2026-04-21 "no priority-type runs this
       week → fall back to execution aggregate across all completed
       runs" locked rule).
    4. ``phase is None`` short-circuits straight to step 3 — there
       is no priority run type to filter on.
    """
    entries_list: List[PriorityKpiDeviation] = list(entries)

    if phase is not None:
        priority_type = priority_run_type_for_phase(phase)
        priority_deviations = [
            e.deviation for e in entries_list if e.run_type_key == priority_type
        ]
        # The filtered set must carry at least one non-None deviation
        # for it to count as "priority runs present".
        if any(d is not None for d in priority_deviations):
            return classify_priority_kpi_execution(priority_deviations)

    # Fallback: all runs in the week, irrespective of type.
    return classify_priority_kpi_execution(e.deviation for e in entries_list)


# --------------------------------------------------------------------- #
# Status matrix
# --------------------------------------------------------------------- #


def classify_weekly_phase_progress(
    band: Optional[AdherenceBand],
    aggregate: Optional[PriorityKpiExecution],
) -> Optional[WeeklyPhaseProgress]:
    """Pure matrix: (band, aggregate) → weekly progress status.

    Returns ``None`` whenever there isn't enough signal to decide —
    specifically when ``band is None`` (empty plan week / future week
    caller) or when ``aggregate is None`` (no completed runs to score).
    Callers that want a firm "nothing this week" label should render
    ``None`` as a soft narrative choice, not as ``off_track``.

    The truth-table mirrors the locked rule:

        band   | aggregate          | status
        -------+--------------------+------------
        High   | mostly_on_target   | on_track
        High   | mixed              | on_track
        High   | mostly_off         | close
        Medium | mostly_on_target   | close
        Medium | mixed              | close
        Medium | mostly_off         | off_track
        Low    | any                | off_track
    """
    if band is None or aggregate is None:
        return None

    if band == AdherenceBand.LOW:
        return WeeklyPhaseProgress.OFF_TRACK

    if band == AdherenceBand.HIGH:
        if aggregate == PriorityKpiExecution.MOSTLY_OFF:
            return WeeklyPhaseProgress.CLOSE
        # mostly_on_target OR mixed → on_track
        return WeeklyPhaseProgress.ON_TRACK

    # AdherenceBand.MEDIUM
    if aggregate == PriorityKpiExecution.MOSTLY_OFF:
        return WeeklyPhaseProgress.OFF_TRACK
    # mostly_on_target OR mixed → close
    return WeeklyPhaseProgress.CLOSE


# --------------------------------------------------------------------- #
# Full composer
# --------------------------------------------------------------------- #


class WeeklyPhaseProgressResult(NamedTuple):
    """Output of :func:`compute_weekly_phase_progress`.

    Every field is JSON-safe. ``status`` is the read-only label the
    coach must not flip; ``aggregate`` and ``band`` are included so
    downstream surfaces (phase analysis payload, retrospective
    narrative) can explain *why* the week got the label it did without
    re-deriving inputs.
    """

    status: Optional[WeeklyPhaseProgress]
    band: Optional[AdherenceBand]
    aggregate: Optional[PriorityKpiExecution]
    priority_run_type: Optional[str]
    priority_run_count: int
    total_run_count: int


def compute_weekly_phase_progress(
    phase: Optional[Phase],
    band: Optional[AdherenceBand],
    entries: Iterable[PriorityKpiDeviation],
) -> WeeklyPhaseProgressResult:
    """Canonical composer — inputs → status + supporting counts.

    Designed so the Phase D payload extension (3D.3 / 3D.7) and the
    coach prompt contract (3D.8) can both consume a single result
    object. Counts are included as transparency for the coach and any
    future diagnostic UI.
    """
    entries_list: List[PriorityKpiDeviation] = list(entries)

    priority_run_type: Optional[str]
    priority_run_count = 0
    if phase is None:
        priority_run_type = None
    else:
        priority_run_type = priority_run_type_for_phase(phase)
        priority_run_count = sum(
            1 for e in entries_list if e.run_type_key == priority_run_type
        )

    aggregate = aggregate_priority_kpi_for_phase(phase, entries_list)
    status = classify_weekly_phase_progress(band, aggregate)

    return WeeklyPhaseProgressResult(
        status=status,
        band=band,
        aggregate=aggregate,
        priority_run_type=priority_run_type,
        priority_run_count=priority_run_count,
        total_run_count=len(entries_list),
    )


__all__ = [
    "MOSTLY_ON_TARGET_MIN_FRACTION",
    "MOSTLY_OFF_MIN_FRACTION",
    "PHASE_PRIORITY_RUN_TYPE",
    "PriorityKpiDeviation",
    "PriorityKpiExecution",
    "WeeklyPhaseProgress",
    "WeeklyPhaseProgressResult",
    "aggregate_priority_kpi_for_phase",
    "classify_priority_kpi_execution",
    "classify_weekly_phase_progress",
    "compute_weekly_phase_progress",
    "priority_run_type_for_phase",
]
