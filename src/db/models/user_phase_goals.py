# src/db/models/user_phase_goals.py

"""
V1.6 Phase D — user-facing "phase focus / goal" storage.

PHASE_3_IMPLEMENTATION_CHECKLIST 3D.1 landing.

Model scope (spec §19.4 "Phase Goals + Progress UX"):
-----------------------------------------------------
Each row captures **the athlete's current focus for a single training
phase** (Base / Build / Peak / Taper) of a single plan. Goals are
behavior / outcome-based (e.g. *"Stay mostly in Zone 2 on long runs"*
— NOT a KPI threshold). There is exactly **one active goal per
(user, plan, phase)** at any time; superseding a goal is an in-place
replacement that soft-history the prior row by flipping its
``status`` to ``superseded`` and inserting a new ``active`` row.

Soft-history over unique constraints
------------------------------------
We deliberately do **not** enforce "one active per (plan, phase)"
with a partial unique index:

* SQLite (used in tests) does not support ``WHERE`` partial indexes
  the same way Postgres does.
* The application-layer ``save_phase_goal`` tool (3D.2) is the single
  writer and will enforce one-active-per-phase by supersede-then-insert
  inside a transaction. Violations require a mis-wired caller, not a
  race, so app-layer enforcement is strictly sufficient for V1.6.

Column rationale
----------------
* ``status`` — lifecycle enum: ``active`` | ``superseded`` | ``completed``
  | ``dropped``. ``completed`` fires only at phase transition (see 3D.4
  retrospective hook); ``dropped`` reserved for future UI "abandon"
  button (V1.7). V1.6 writers only produce ``active`` / ``superseded`` /
  ``completed``.
* ``source`` — provenance enum: ``auto_proposed`` | ``coach_refined`` |
  ``user_stated``. Lets the coach reference tone differently
  ("Here's what I suggested for this phase …" vs. "Your stated focus
  for this phase …") without re-deriving intent from the goal text.
* ``confirmed_at`` — nullable timestamp; set when the athlete agrees
  to an auto-proposed goal (even a soft "sounds good" in chat). ``None``
  means the goal is live in the backend but not yet explicitly
  acknowledged by the user. The coach still narrates it, per the UX
  spec's "no hard consent gates" rule, but the prompt contract can key
  tone off ``confirmed_at is None`` for a softer frame.

See also
--------
* :mod:`src.services.phase.phase_priority` — canonical ``Phase`` enum
  (wire-compatible with this column's string values).
* :mod:`src.services.phase.weekly_progress` — 3D.6 classifier that
  expresses how the current week is tracking against the active goal.
* ``migrations/sql/20260421_create_user_phase_goals.sql`` — forward/
  rollback DDL for Railway Postgres. ORM ``Base.metadata.create_all``
  handles dev + test fresh databases automatically.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    TIMESTAMP,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.db_session import Base


# Status lifecycle — exposed as module constants so tools, services,
# and tests reference the same strings. V1.6 writers produce only the
# first three.
GOAL_STATUS_ACTIVE = "active"
GOAL_STATUS_SUPERSEDED = "superseded"
GOAL_STATUS_COMPLETED = "completed"
GOAL_STATUS_DROPPED = "dropped"

GOAL_STATUS_VALUES = (
    GOAL_STATUS_ACTIVE,
    GOAL_STATUS_SUPERSEDED,
    GOAL_STATUS_COMPLETED,
    GOAL_STATUS_DROPPED,
)

# Provenance of the goal text — informs coach tone (§19.4) and the
# "was this proposed or stated?" retrospective framing.
GOAL_SOURCE_AUTO_PROPOSED = "auto_proposed"
GOAL_SOURCE_COACH_REFINED = "coach_refined"
GOAL_SOURCE_USER_STATED = "user_stated"

GOAL_SOURCE_VALUES = (
    GOAL_SOURCE_AUTO_PROPOSED,
    GOAL_SOURCE_COACH_REFINED,
    GOAL_SOURCE_USER_STATED,
)


class UserPhaseGoal(Base):
    """V1.6 Phase D row — one focus per (user, plan, phase, version)."""

    __tablename__ = "user_phase_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id = Column(
        Integer,
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Canonical ``plans_workouts.phase`` string — "Base" / "Build" /
    # "Peak" / "Taper". Not an Enum column so the Phase enum can be
    # extended in a future spec without a migration.
    phase = Column(String(16), nullable=False)

    # Human-readable focus sentence the coach and UI render verbatim.
    # V1.6 tools cap length at the app layer; the DB stays permissive.
    goal_text = Column(Text, nullable=False)

    # Lifecycle — see module constants. Stored as String(16) rather
    # than a Postgres-native ENUM so dev / test databases don't need
    # a migration to evolve the enum. App-layer validators enforce
    # the allowed set.
    status = Column(
        String(16),
        nullable=False,
        server_default=GOAL_STATUS_ACTIVE,
    )

    # Provenance — see module constants.
    source = Column(
        String(32),
        nullable=False,
        server_default=GOAL_SOURCE_AUTO_PROPOSED,
    )

    # Explicit user acknowledgement timestamp. ``None`` = proposed but
    # not confirmed. The UX spec forbids a hard consent gate, so the
    # coach still narrates unconfirmed goals; this field exists for
    # tone shaping (§19.4) and audit.
    confirmed_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    # ``updated_at`` intentionally omitted — the table is append-mostly
    # (supersede → insert new row). V1.6 does not need in-place edits
    # to active goals; a text fix is modeled as supersede+insert.

    user = relationship("UserIdentity")
    plan = relationship("Plan")


# Non-unique composite index — the hottest read is "give me the active
# goal for (user, plan, phase)" and its chronological neighbours. A
# partial unique index would be ideal but portability rules it out; see
# module docstring for the app-layer enforcement rationale.
Index(
    "ix_user_phase_goals_lookup",
    UserPhaseGoal.user_id,
    UserPhaseGoal.plan_id,
    UserPhaseGoal.phase,
    UserPhaseGoal.status,
    UserPhaseGoal.created_at.desc(),
)


__all__ = [
    "UserPhaseGoal",
    "GOAL_STATUS_ACTIVE",
    "GOAL_STATUS_SUPERSEDED",
    "GOAL_STATUS_COMPLETED",
    "GOAL_STATUS_DROPPED",
    "GOAL_STATUS_VALUES",
    "GOAL_SOURCE_AUTO_PROPOSED",
    "GOAL_SOURCE_COACH_REFINED",
    "GOAL_SOURCE_USER_STATED",
    "GOAL_SOURCE_VALUES",
]
