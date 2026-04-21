"""
Canonical producer for V1.6 §8 ``phase_kpi_priority`` ordered list
and the V1.6 §7 "Phase Transition Weeks" majority-of-days rule.

PHASE_3_IMPLEMENTATION_CHECKLIST §X.5 single-source-of-truth: this
module is the ONLY place in the codebase that maps a training phase
to its ordered KPI-emphasis list OR resolves the phase for a
calendar week that spans a phase boundary. All coach payloads, Phase
B plan-aware tools (``get_weekly_plan``, ``get_phase_analysis``),
the prompt builder's §19.4 phase-aware emphasis, and the coach
response validator's "no overriding ``phase_kpi_priority``" check
MUST consume the helpers below — never reimplement the per-phase
table, never mirror it on mobile, never let the LLM derive or
contradict it (V1.6 §19 LLM contract).

Spec references (SMARTCOACH_SYSTEM_SPEC_V1.md)
-----------------------------------------------
§7 "Phase Transition Weeks" — majority-of-days rule with later-
phase tie-break:

    Weeks that span a phase boundary (e.g. the last week of Base,
    first week of Build) use the majority-of-days rule: the phase
    that owns 4 or more of the 7 calendar days in the week is the
    phase used for phase_kpi_priority that week. Ties (3/3/1 splits
    across a sliver of a third phase, or 3/4 splits at a transition)
    resolve to the later phase to prepare the athlete for what's
    coming next.

§8 "phase_kpi_priority (Deterministic, V1.6)" — per-phase ordered
emphasis list:

    Base   → HR Drift, Aerobic Efficiency, Easy zone compliance
    Build  → Pace Consistency (Tempo), Quality zone compliance,
             HR Drift
    Peak   → Execution (zone compliance across Tempo + Long),
             Fatigue consistency (HR drift across the week),
             Pace Consistency
    Taper  → Maintenance (maintain not improve), Recovery signals,
             Zone compliance

    "The coach must weight its per-week narrative toward the top
    1–2 entries in this list (§19.4). The full KPI set is still
    computed per run type; priority only governs what the coach
    talks about."

Derivation policy — on-read, not persisted
------------------------------------------
Like ``plan_status``, ``baseline_status``, ``deviation_direction``,
and ``adherence_runs_pct``, ``phase_kpi_priority`` is derived on
read from the underlying ``plan_workouts.phase`` column. Persistence
would require invalidation every time a generator or adaptation
pass rewrites a workout's phase; the lookup is trivially fast so
the trade-off is always in favor of re-compute.

Phase resolution policy for a week
----------------------------------
The spec wording "7 calendar days" implies a per-calendar-day
phase assignment. In practice only training days carry a phase
(``plan_workouts.phase`` rows are created per workout; rest days
have no row). The canonical producer therefore operates on the
sequence of per-workout phase labels the caller passes in and
treats it as the evidence base:

    * **Plurality** wins (not strict majority) — a 3/2/1 split
      across Mon/Wed/Thu/Sat training days still has a clear
      emphasis that the coach should follow. The spec's "4 or more
      of 7" rule is a sufficient condition but not a necessary one
      when non-training days don't contribute evidence. Callers
      that need true calendar-day semantics (e.g. Phase B
      ``get_weekly_plan`` once it carries-forward phases onto rest
      days) can pass 7 entries to recover the strict §7 reading.
    * **Later-phase tie-break** — when two or more phases tie at
      the top count, the winner is the latest in training order
      ``Base < Build < Peak < Taper``. This matches spec §7
      "resolve to the later phase to prepare the athlete for
      what's coming next".
    * **All-None / empty input** yields ``phase=None`` — there is
      no evidence for an emphasis list; callers must degrade
      gracefully (omit the ``phase_kpi_priority`` block from the
      payload rather than fabricate a phase).

KPI identifiers
---------------
Each priority entry is a machine-readable ``kpi_id`` string plus a
spec-accurate ``label``:

* ``kpi_id`` is stable across the backend, mobile, and LLM prompts
  — the coach response validator (§19.1) keys on it to detect the
  LLM fabricating a non-canonical KPI.
* ``label`` mirrors the spec §8 wording verbatim so the LLM prompt
  and UI read naturally without re-translating.

The ordered pair is emitted together so mobile / coach can pick
whichever is appropriate for their surface without having to host
their own mapping.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple


class Phase(str, Enum):
    """V1.6 training phases. String base makes JSON serialization trivial.

    The wire values match the canonical ``plan_workouts.phase`` column
    strings so the DB value can be passed straight through
    ``Phase(value)`` without a translation layer.
    """

    BASE = "Base"
    BUILD = "Build"
    PEAK = "Peak"
    TAPER = "Taper"


# Ordering for the spec §7 "later phase" tie-breaker. Higher integer
# wins ties. Kept as a module constant so tests can assert the
# ordering independently of alphabet / enum iteration order.
_PHASE_ORDER: Dict[Phase, int] = {
    Phase.BASE: 0,
    Phase.BUILD: 1,
    Phase.PEAK: 2,
    Phase.TAPER: 3,
}


class PhaseKpi(NamedTuple):
    """One entry in the ``phase_kpi_priority`` ordered list.

    Fields
    ------
    kpi_id
        Machine-readable stable identifier. Matches the §19.1
        validator's allow-list of canonical KPI IDs.
    label
        Human-readable label, spec-verbatim, for direct use in the
        LLM prompt and UI surfaces.
    """

    kpi_id: str
    label: str


# Canonical §8 table — the single in-code embodiment of the spec
# mapping. The ordering of each list is the spec's "highest first"
# order; callers MUST NOT reorder.
_PHASE_KPI_PRIORITY: Dict[Phase, Tuple[PhaseKpi, ...]] = {
    Phase.BASE: (
        PhaseKpi("hr_drift", "HR Drift"),
        PhaseKpi("aerobic_efficiency", "Aerobic Efficiency"),
        PhaseKpi("easy_zone_compliance", "Easy zone compliance"),
    ),
    Phase.BUILD: (
        PhaseKpi("pace_consistency_tempo", "Pace Consistency (Tempo)"),
        PhaseKpi("quality_zone_compliance", "Quality zone compliance"),
        PhaseKpi("hr_drift", "HR Drift"),
    ),
    Phase.PEAK: (
        PhaseKpi(
            "execution_zone_compliance",
            "Execution (zone compliance across Tempo + Long)",
        ),
        PhaseKpi(
            "fatigue_consistency",
            "Fatigue consistency (HR drift across the week)",
        ),
        PhaseKpi("pace_consistency", "Pace Consistency"),
    ),
    Phase.TAPER: (
        PhaseKpi("maintenance", "Maintenance (maintain not improve)"),
        PhaseKpi("recovery_signals", "Recovery signals"),
        PhaseKpi("zone_compliance", "Zone compliance"),
    ),
}


class PhaseKpiPriorityResult(NamedTuple):
    """Output of :func:`compute_phase_kpi_priority_for_week`.

    Fields
    ------
    phase
        The resolved phase for the week, or ``None`` when the input
        contained no usable evidence (all entries ``None`` or
        unknown).
    priority
        Ordered tuple of :class:`PhaseKpi` — the exact spec §8 list
        for ``phase`` (length 3 for all four phases in V1.6). Empty
        tuple iff ``phase is None``.
    day_counts
        ``phase_value -> count`` for every phase that contributed
        at least one day of evidence. Useful for (a) debugging
        transition weeks, (b) §19.4 coach narrative ("this week is
        primarily Build — 5 of your 6 sessions are in Build"), and
        (c) Phase B ``get_phase_analysis`` surface.
    """

    phase: Optional[Phase]
    priority: Tuple[PhaseKpi, ...]
    day_counts: Dict[str, int]


def phase_kpi_priority_for_phase(phase: Phase) -> Tuple[PhaseKpi, ...]:
    """
    Pure lookup of the §8 ordered emphasis list for a single phase.

    Returns an immutable tuple so callers cannot mutate the canonical
    table. V1.6 emits exactly three entries for all four phases; the
    contract does not guarantee that length across spec versions
    (tests lock it for V1.6).
    """
    return _PHASE_KPI_PRIORITY[phase]


def resolve_week_phase(phases: Iterable[Optional[str]]) -> Optional[Phase]:
    """
    Apply the V1.6 §7 majority-of-days rule to a week's per-day /
    per-workout phase labels.

    Args:
        phases: One entry per day (or per workout) in the target
            week. Each entry is either the canonical phase string
            (``"Base"`` / ``"Build"`` / ``"Peak"`` / ``"Taper"``) or
            ``None`` for days with no phase evidence (rest days,
            unassigned workouts). Unknown non-canonical strings are
            silently skipped — the producer never raises on bad
            inputs because the coach tier is a hot path and §19
            "deterministic correctness" prefers "omit the emphasis
            block" over "crash the response".

    Returns:
        The winning :class:`Phase`, or ``None`` when no entry is a
        canonical phase value.

    Tie-breaking:
        When two or more phases tie at the top count, the later
        phase in training order (``Base < Build < Peak < Taper``)
        wins, per spec §7 "resolve to the later phase to prepare
        the athlete for what's coming next".
    """
    counts: Dict[Phase, int] = {}
    for raw in phases:
        if raw is None:
            continue
        try:
            phase = Phase(raw)
        except ValueError:
            # Bad phase string — skip rather than crash. The LLM-
            # facing contract is "we emit what we can prove"; a
            # stray legacy value must not take the whole week's
            # emphasis offline.
            continue
        counts[phase] = counts.get(phase, 0) + 1

    if not counts:
        return None

    # Rank by (count desc, phase order desc) so the later phase
    # wins ties naturally.
    ranked = sorted(
        counts.items(),
        key=lambda kv: (kv[1], _PHASE_ORDER[kv[0]]),
        reverse=True,
    )
    return ranked[0][0]


def compute_phase_kpi_priority_for_week(
    phases: Iterable[Optional[str]],
) -> PhaseKpiPriorityResult:
    """
    Composed entry point used by route / tool callers.

    Takes the week's per-day (or per-workout) phase labels, resolves
    the winning phase via :func:`resolve_week_phase`, and returns
    the §8 ordered KPI list for it together with the day-count
    breakdown for downstream narrative.

    A single full-materialization (list comprehension over ``phases``
    is deliberate because we iterate twice (once for counts, once
    implicitly via the returned ``day_counts``); callers pass small
    collections (≤ 7 week-days or ≤ ~10 workouts) so the copy is
    negligible vs. the clarity of having a stable snapshot.
    """
    materialized = list(phases)
    phase = resolve_week_phase(materialized)
    if phase is None:
        return PhaseKpiPriorityResult(
            phase=None,
            priority=(),
            day_counts={},
        )

    day_counts: Dict[str, int] = {}
    for raw in materialized:
        if raw is None:
            continue
        try:
            Phase(raw)
        except ValueError:
            continue
        day_counts[raw] = day_counts.get(raw, 0) + 1

    return PhaseKpiPriorityResult(
        phase=phase,
        priority=phase_kpi_priority_for_phase(phase),
        day_counts=day_counts,
    )


__all__ = [
    "Phase",
    "PhaseKpi",
    "PhaseKpiPriorityResult",
    "compute_phase_kpi_priority_for_week",
    "phase_kpi_priority_for_phase",
    "resolve_week_phase",
]
