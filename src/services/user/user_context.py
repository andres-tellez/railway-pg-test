"""
Canonical builder for the V1.6 Phase B 3B.10 ``user_context`` payload.

Single source of truth (PHASE_3_IMPLEMENTATION_CHECKLIST §X.5) for the
user-level context block the coach reads at the **start** of a
conversation / new turn when ``turn_type == "opening"`` (per §19
orchestrator nudge, wired in 3B.13). Consumers:

* **LLM agent tool** ``get_user_context()`` in
  :mod:`src.smartcoach_mobile_coach.agent_tools` — thin wrapper,
  emits the service output verbatim.

There is no HTTP route consumer in V1.6; the payload is coach-facing
only. If a mobile "my training context" card wants the same data later
it MUST call this builder so the surfaces don't drift.

Spec references (SMARTCOACH_SYSTEM_SPEC_V1.md + AGENTIC_COACH.md Topic 9)
-------------------------------------------------------------------------
* Race goal (name / date / distance / goal_time / primary_goal /
  weeks_until_race).
* ``baseline_status`` — produced by
  :func:`src.services.baseline.baseline_status.compute_baseline_status_for_athlete`.
* Current training phase — produced by
  :func:`src.services.phase.phase_priority.resolve_week_phase` on the
  current week's ``plan_workouts.phase`` values, with the canonical §8
  ``phase_kpi_priority`` attached.
* ``coaching_level`` / ``verbosity`` / stored per-surface metric
  priorities — read from ``user_coach_preferences`` (written by
  ``tool_save_coach_preference``).
* Stated preferences (training days, long-run day, unit system) —
  ``plans.training_days`` + derivation from ``plan_workouts``.
* Session summary — Phase F populates the latest curated row as a small
  object; ``None`` when none exists.
* Plan memories — Phase F ``user_plan_memories`` rows (coach tool +
  optional summarizer).

Derivation policy — on-read, not persisted
------------------------------------------
The payload is a pure composition over already-persisted inputs. No
field in this module is computed or persisted here — each signal has a
canonical producer elsewhere (baseline / phase / adherence modules).
This keeps §X.5 intact: ``get_user_context`` is a **reader**, never a
producer.

Payload size budget (3B.11)
---------------------------
Target < 2 KB. The current shape lands ~700-900 bytes for a fully
populated user (race goal + active plan + all preferences). Keys are
stable (documented in the service docstring + locked by the contract
test) so the LLM can learn them once.

PII posture (3B.11)
-------------------
No field in this payload is PII beyond what already lives on
``user_identity`` / ``user_profile`` — which the coach already has
grounds to see. We deliberately emit only the first-token of
``user_identity.name`` as ``display_name`` (no email, no picture URL,
no auth provider metadata).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.user_coach_preferences import UserCoachPreferences
from src.db.models.session_summaries import SessionSummary
from src.db.models.user_identity import UserIdentity
from src.db.models.user_profile import UserProfile
from src.services.coach.user_plan_memory_service import memories_for_user_context
from src.services.baseline.baseline_status import (
    BaselineStatus,
    compute_baseline_status_for_athlete,
)
from src.services.phase.phase_priority import (
    PhaseKpi,
    phase_kpi_priority_for_phase,
    resolve_week_phase,
)
from src.utils.date_helpers import get_week_bounds_for_date
from src.utils.timezone_helpers import get_today_date_in_timezone

logger = logging.getLogger(__name__)

_WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Payload schema version. Bump on any breaking shape change so the
# coach prompt / validator can refuse unknown versions rather than
# silently mis-key the payload.
USER_CONTEXT_SCHEMA_VERSION = 2

# Default coaching-preference values mirror the column ``server_default``
# on :class:`UserCoachPreferences`. Kept here so the payload has a
# canonical "no row yet" shape (row only gets created when the user
# saves a preference via ``tool_save_coach_preference``).
_DEFAULT_COACHING_LEVEL = "beginner"
_DEFAULT_VERBOSITY = "normal"


def _first_name_only(raw_name: Optional[str]) -> Optional[str]:
    """Return the first whitespace-delimited token of ``raw_name``.

    Emitting only the first name limits PII surface area (the coach
    never needs a full legal name to be warm) while still giving the
    LLM a greet-able token.
    """
    if not isinstance(raw_name, str):
        return None
    cleaned = raw_name.strip()
    if not cleaned:
        return None
    return cleaned.split()[0]


def _coerce_date(value: Any) -> Optional[date]:
    """Best-effort ``date`` coercion for ``Plan.race_date`` reads."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.split("T")[0]).date()
        except ValueError:
            return None
    return None


def _load_active_or_most_recent_plan(session: Session, user_id: UUID) -> Optional[Plan]:
    """Load the plan we render context against, or ``None``.

    Mirrors :func:`src.services.plan.weekly_plan._load_active_or_most_recent_plan`
    so every plan-read surface agrees on "which plan is this user on".
    """
    plan = (
        session.query(Plan)
        .filter(Plan.user_id == user_id, Plan.is_active.is_(True))
        .order_by(Plan.created_at.desc())
        .first()
    )
    if plan is not None:
        return plan
    return (
        session.query(Plan)
        .filter(Plan.user_id == user_id)
        .order_by(Plan.created_at.desc())
        .first()
    )


def _load_user_identity(session: Session, user_id: UUID) -> Optional[UserIdentity]:
    return (
        session.query(UserIdentity)
        .filter(UserIdentity.user_id == user_id)
        .one_or_none()
    )


def _load_user_profile(session: Session, user_id: UUID) -> Optional[UserProfile]:
    return (
        session.query(UserProfile)
        .filter(UserProfile.user_id == str(user_id))
        .one_or_none()
    )


def _load_user_coach_preferences(
    session: Session, user_id: UUID
) -> Optional[UserCoachPreferences]:
    return (
        session.query(UserCoachPreferences)
        .filter(UserCoachPreferences.user_id == user_id)
        .one_or_none()
    )


def _load_primary_athlete_id(session: Session, user_id: UUID) -> Optional[int]:
    link = (
        session.query(UserAthleteLink.athlete_id)
        .filter(UserAthleteLink.user_id == str(user_id))
        .order_by(UserAthleteLink.id.asc())
        .first()
    )
    if link is None:
        return None
    try:
        return int(link[0])
    except (TypeError, ValueError):
        return None


def _compute_race_goal(plan: Plan, today: date) -> Optional[Dict[str, Any]]:
    """Race-goal block — ``None`` when the plan has no race date.

    ``weeks_until_race`` is a floor-division of days remaining; a race
    today yields ``0`` (not ``None``) so the coach can narrate "race
    week" correctly. Past races yield negative values — those get
    clamped to ``None`` since a past race is no longer a goal.
    """
    race_date = _coerce_date(plan.race_date)
    race_name = plan.race_name
    race_distance = plan.race_distance
    goal_time = plan.target_time
    primary_goal = plan.primary_goal

    has_any = any(
        [race_date is not None, race_name, race_distance, goal_time, primary_goal]
    )
    if not has_any:
        return None

    weeks_until: Optional[int] = None
    if race_date is not None:
        delta_days = (race_date - today).days
        if delta_days >= 0:
            weeks_until = delta_days // 7

    return {
        "race_name": race_name or None,
        "race_distance": race_distance or None,
        "race_date": race_date.isoformat() if race_date else None,
        "goal_time": goal_time or None,
        "primary_goal": primary_goal or None,
        "weeks_until_race": weeks_until,
    }


def _load_plan_date_bounds(
    session: Session, plan_id: int
) -> tuple[Optional[date], Optional[date]]:
    """Return ``(first_workout_date, last_workout_date)`` for the plan.

    Uses plan_workouts rather than a stored plan_start/plan_end so the
    bounds are always consistent with what the user actually has on
    their calendar (plan generator doesn't currently persist an
    explicit plan-end).
    """
    first = (
        session.query(PlanWorkout.date)
        .filter(PlanWorkout.plan_id == plan_id)
        .order_by(PlanWorkout.date.asc())
        .first()
    )
    last = (
        session.query(PlanWorkout.date)
        .filter(PlanWorkout.plan_id == plan_id)
        .order_by(PlanWorkout.date.desc())
        .first()
    )
    first_date = first[0] if first else None
    last_date = last[0] if last else None
    return first_date, last_date


def _derive_current_week_number(
    plan_first_date: Optional[date], today: date
) -> Optional[int]:
    """1-indexed current week of the plan, or ``None`` when out of bounds.

    Uses the plan's first training Monday as week 1 anchor. Today before
    the plan starts → ``None``. Today after the plan ends is handled by
    the caller (this helper does not cap).
    """
    if plan_first_date is None:
        return None
    # Normalize to the Monday of the first training week so a plan that
    # happens to start on, say, Wednesday still has "week 1" spanning
    # the whole Mon-Sun window.
    first_week_monday = get_week_bounds_for_date(plan_first_date)[0]
    current_week_monday = get_week_bounds_for_date(today)[0]
    delta_days = (current_week_monday - first_week_monday).days
    if delta_days < 0:
        return None
    return (delta_days // 7) + 1


def _compute_current_phase_block(
    session: Session,
    plan_id: int,
    today: date,
) -> Optional[Dict[str, Any]]:
    """Return ``{"phase": "Build", "phase_kpi_priority": [...]}`` or ``None``.

    Resolves the phase of the current calendar week (Mon-Sun containing
    ``today``) using the canonical §7 majority-of-days rule, then
    attaches the canonical §8 emphasis list. ``None`` when the current
    week has no planned workouts (before plan start, after plan end,
    or a gap week).
    """
    week_start, week_end = get_week_bounds_for_date(today)
    rows = (
        session.query(PlanWorkout.phase)
        .filter(
            PlanWorkout.plan_id == plan_id,
            PlanWorkout.date >= week_start,
            PlanWorkout.date <= week_end,
        )
        .all()
    )
    if not rows:
        return None

    phase = resolve_week_phase([r[0] for r in rows])
    if phase is None:
        return None

    priority: List[PhaseKpi] = list(phase_kpi_priority_for_phase(phase))
    return {
        "phase": phase.value,
        "phase_kpi_priority": [
            {"kpi_id": kpi.kpi_id, "label": kpi.label} for kpi in priority
        ],
    }


def _derive_long_run_day(session: Session, plan_id: int) -> Optional[str]:
    """Find the most common long-run weekday across the plan.

    Uses ``run_type_key == 'long'`` on ``plan_workouts``. Returns a
    3-letter label (``"Sat"``) to match ``plans.training_days`` wire
    format. ``None`` when the plan has no long runs (very short plans,
    intake mid-generation).
    """
    rows = (
        session.query(PlanWorkout.date)
        .filter(
            PlanWorkout.plan_id == plan_id,
            PlanWorkout.run_type_key == "long",
        )
        .all()
    )
    if not rows:
        return None

    counts: Dict[int, int] = {}
    for (d,) in rows:
        if d is None:
            continue
        wd = d.weekday()
        counts[wd] = counts.get(wd, 0) + 1

    if not counts:
        return None

    best_wd, _best_count = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))
    return _WEEKDAY_LABELS[best_wd]


def _compute_plan_block(
    session: Session,
    plan: Plan,
    today: date,
) -> Dict[str, Any]:
    """Active-plan block with plan_start / plan_end / current_week_number /
    current phase + emphasis list.
    """
    first_date, last_date = _load_plan_date_bounds(session, plan.id)
    current_week = _derive_current_week_number(first_date, today)

    total_weeks: Optional[int]
    if first_date is not None and last_date is not None:
        # Convert both to their Monday anchors so partial-week tails
        # don't under-count (a 12-week plan that happens to end on a
        # Wednesday is still 12 weeks).
        first_monday = get_week_bounds_for_date(first_date)[0]
        last_monday = get_week_bounds_for_date(last_date)[0]
        total_weeks = ((last_monday - first_monday).days // 7) + 1
    else:
        total_weeks = None

    current_phase_block = _compute_current_phase_block(session, plan.id, today)

    block: Dict[str, Any] = {
        "plan_id": int(plan.id),
        "plan_name": plan.plan_name,
        "plan_start": first_date.isoformat() if first_date else None,
        "plan_end": last_date.isoformat() if last_date else None,
        "total_weeks": total_weeks,
        "current_week_number": current_week,
        "is_active": bool(plan.is_active),
    }
    if current_phase_block is not None:
        block["current_phase"] = current_phase_block["phase"]
        block["phase_kpi_priority"] = current_phase_block["phase_kpi_priority"]
    else:
        block["current_phase"] = None
        block["phase_kpi_priority"] = None
    return block


def _compute_coaching_block(
    prefs: Optional[UserCoachPreferences],
) -> Dict[str, Any]:
    if prefs is None:
        return {
            "coaching_level": _DEFAULT_COACHING_LEVEL,
            "verbosity": _DEFAULT_VERBOSITY,
            "run_summary_priority": None,
            "training_summary_priority": None,
            "has_saved_preferences": False,
        }
    return {
        "coaching_level": prefs.coaching_level or _DEFAULT_COACHING_LEVEL,
        "verbosity": prefs.verbosity or _DEFAULT_VERBOSITY,
        "run_summary_priority": prefs.run_summary_priority or None,
        "training_summary_priority": prefs.training_summary_priority or None,
        "has_saved_preferences": True,
    }


def _latest_session_summary_for_context(
    session: Session, user_id: UUID
) -> Optional[Dict[str, Any]]:
    """Most recent Layer B summary as a compact object for ``get_user_context``."""
    try:
        row = (
            session.query(SessionSummary)
            .filter(SessionSummary.user_id == user_id)
            .order_by(SessionSummary.created_at.desc())
            .first()
        )
    except Exception:
        logger.debug(
            "session_summaries read failed in user_context; treating as absent",
            exc_info=True,
        )
        return None
    if row is None:
        return None
    text = (row.summary_text or "").strip()
    if not text:
        return None
    excerpt = text if len(text) <= 500 else text[:497].rstrip() + "…"
    raw_tags = row.thread_tags
    tags: List[str] = []
    if isinstance(raw_tags, list):
        for t in raw_tags[:8]:
            if isinstance(t, str) and t.strip():
                tags.append(t.strip())
    created = row.created_at
    created_iso: Optional[str] = None
    if isinstance(created, datetime):
        c = created
        if c.tzinfo is None:
            c = c.replace(tzinfo=timezone.utc)
        created_iso = c.replace(microsecond=0).isoformat()
    return {
        "excerpt": excerpt,
        "thread_tags": tags,
        "created_at": created_iso,
    }


def _compute_preferences_block(
    session: Session,
    plan: Optional[Plan],
    profile: Optional[UserProfile],
    tz: str,
) -> Dict[str, Any]:
    training_days: Optional[List[str]] = None
    long_run_day: Optional[str] = None
    if plan is not None:
        raw_days = plan.training_days
        if isinstance(raw_days, list):
            cleaned = [str(d).strip() for d in raw_days if str(d).strip()]
            training_days = cleaned or None
        long_run_day = _derive_long_run_day(session, plan.id)

    unit_system: Optional[str] = None
    if profile is not None:
        unit_system = profile.unit_system or None

    return {
        "training_days": training_days,
        "long_run_day": long_run_day,
        "unit_system": unit_system,
        "timezone": tz,
    }


def build_user_context_payload(
    session: Session,
    user_id: UUID,
    *,
    tz: str = "UTC",
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Build the V1.6 Phase B 3B.10 ``user_context`` payload.

    Args:
        session: Active SQLAlchemy session.
        user_id: Internal user UUID (not Auth0 subject).
        tz: IANA timezone name; used to resolve "today" and emitted in
            ``preferences.timezone``. Defaults to UTC.
        today: Explicit "today" override (primarily for tests). When
            supplied, ``tz`` still drives the emitted ``preferences.
            timezone`` field but does not affect the resolution.

    Returns:
        Either an error envelope
        (``{"error": "no_user", "message": ...}``) when the user has no
        ``user_identity`` row, or the full context payload:

        ``{
            "schema_version": 1,
            "user_id": "<uuid>",
            "display_name": "Jane" | None,
            "baseline_status": "insufficient" | "thin" | "strong" | None,
            "race_goal": {...} | None,
            "plan": {...} | None,
            "coaching": {...},
            "preferences": {...},
            "plan_memories": [{id, text, source, created_at, memory_type?}, ...],
            "session_summary": null | {excerpt, thread_tags, created_at},
            "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
            "today": "YYYY-MM-DD"
        }``

    Never raises on missing data — absent signals become explicit
    ``None`` / default values. The coach-side contract is "what is
    present is authoritative; what is None is simply not known yet".

    V1.6 contracts enforced by delegation:
        * §X.5 — every deterministic value is read off the canonical
          producer (``compute_baseline_status_for_athlete``,
          ``resolve_week_phase``, ``phase_kpi_priority_for_phase``).
          This module never re-derives a signal.
        * §19 — no PII beyond what ``user_identity`` / ``user_profile``
          already carry; only the first name is emitted.
    """
    if not isinstance(tz, str) or not tz.strip():
        tz_norm = "UTC"
    else:
        tz_norm = tz.strip()

    resolved_today: date = (
        today if today is not None else get_today_date_in_timezone(tz_norm)
    )

    identity = _load_user_identity(session, user_id)
    if identity is None:
        # We deliberately still emit a ``user_context`` for anonymous /
        # test harnesses IF a plan exists, but V1.6 surfaces all flow
        # through auth so a missing identity row is effectively "bad
        # user id" and surfaced as a tool error.
        return {
            "error": "no_user",
            "message": "No user identity found for this account.",
        }

    plan = _load_active_or_most_recent_plan(session, user_id)
    profile = _load_user_profile(session, user_id)
    prefs = _load_user_coach_preferences(session, user_id)
    athlete_id = _load_primary_athlete_id(session, user_id)

    baseline_value: Optional[str] = None
    if athlete_id is not None:
        try:
            baseline = compute_baseline_status_for_athlete(
                session, athlete_id, today=resolved_today
            )
            baseline_value = (
                baseline.value if isinstance(baseline, BaselineStatus) else None
            )
        except Exception:
            # Producer contract: returns BaselineStatus, never raises.
            # Belt-and-suspenders: a DB hiccup here must not take the
            # whole context payload offline — the coach can still read
            # the plan / preferences blocks.
            logger.warning(
                "baseline_status producer raised; continuing with null",
                exc_info=True,
            )
            baseline_value = None

    race_goal_block: Optional[Dict[str, Any]] = None
    plan_block: Optional[Dict[str, Any]] = None
    if plan is not None:
        race_goal_block = _compute_race_goal(plan, resolved_today)
        plan_block = _compute_plan_block(session, plan, resolved_today)

    plan_memories_block = memories_for_user_context(session, user_id)
    session_summary_block = _latest_session_summary_for_context(session, user_id)

    payload: Dict[str, Any] = {
        "schema_version": USER_CONTEXT_SCHEMA_VERSION,
        "user_id": str(user_id),
        "display_name": _first_name_only(identity.name),
        "baseline_status": baseline_value,
        "race_goal": race_goal_block,
        "plan": plan_block,
        "coaching": _compute_coaching_block(prefs),
        "preferences": _compute_preferences_block(session, plan, profile, tz_norm),
        "plan_memories": plan_memories_block,
        "session_summary": session_summary_block,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "today": resolved_today.isoformat(),
    }
    return payload


__all__ = [
    "USER_CONTEXT_SCHEMA_VERSION",
    "build_user_context_payload",
]
