"""
Central vocabulary for running / training terminology.

This module is the **single source of truth** for canonical workout-type strings,
human-facing descriptions, basic training rules, and heart-rate / effort zone
placeholders used across the product.

**Convention for engineers**

- New features in plan generation, insights, coach responses, and APIs should
  import labels and rules from here (or from thin wrappers) so wording and
  identifiers stay consistent.
- Today, several legacy modules still own overlapping constants (for example
  ``src.services.training_plan.v2.workout_taxonomy.workout_definitions`` and
  ``src.services.training_plan.workout_types``). Those remain authoritative for
  runtime behavior until they are migrated; the values below are aligned with
  them **at the time this module was introduced**—no renames, no behavior change.

This module is **additive only**: it does not patch or replace existing imports.

**Taxonomy vs placement roles**

- ``WORKOUT_TYPES``: **workout taxonomy** — keys used to classify workouts, attach
  definitions, and drive Pass3–Pass7 behavior (e.g. ``long_run``, ``tempo``,
  ``intervals``). Do not use these strings interchangeably with placement roles.
- ``PLACEMENT_ROLE_TYPES``: **placement roles** — coarse roles used when splitting
  weekly mileage across training days (e.g. ``easy``, ``steady``, ``endurance``,
  ``long`` from ``workout_types``). Scheduling and templates reason in this space.
- The two sets are **intentionally different** and must not be mixed; a single
  day may map from roles to taxonomy types via plan logic, not by assuming the
  same string sets.

**Role → taxonomy default map**

- ``ROLE_TO_TAXONOMY_MAP`` maps each **placement role** to a representative
  **taxonomy** key. It is for **interpretation** (insights, coach copy, analytics),
  **not** for enforcement of plan structure. Plan generation may still apply
  templates, phase rules, and other constraints beyond this table.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Mapping

# -----------------------------------------------------------------------------
# WORKOUT_TYPES — workout taxonomy (classification, definitions, Pass3–Pass7)
# Matches keys in ``workout_taxonomy.workout_definitions.WORKOUT_DEFINITIONS``.
# -----------------------------------------------------------------------------

_WORKOUT_DEFINITIONS_CORE: Dict[str, Dict[str, str]] = {
    "long_run": {
        "description": "Steady easy long run for aerobic endurance",
        "purpose": "endurance",
    },
    "easy": {
        "description": "Easy aerobic run for recovery and base building",
        "purpose": "recovery",
    },
    "recovery": {
        "description": "Very easy jog for active recovery",
        "purpose": "active_recovery",
    },
    "steady": {
        "description": "Controlled aerobic run at steady effort; not hard",
        "purpose": "aerobic",
    },
    "tempo": {
        "description": "Sustained effort at lactate threshold pace",
        "purpose": "lactate_threshold",
    },
    "intervals": {
        "description": "High-intensity repeats with recovery jogs between",
        "purpose": "vo2max",
    },
    "hills": {
        "description": "Hill repeats for running-specific strength and power",
        "purpose": "strength",
    },
    "threshold": {
        "description": "Cruise intervals at threshold pace with short recovery",
        "purpose": "lactate_threshold",
    },
    "fartlek": {
        "description": "Unstructured speed play mixing easy and moderate efforts",
        "purpose": "aerobic_speed",
    },
}

WORKOUT_TYPES: FrozenSet[str] = frozenset(_WORKOUT_DEFINITIONS_CORE.keys())

# Descriptions + purpose only (expand in this layer over time).
WORKOUT_DEFINITIONS: Mapping[str, Dict[str, str]] = dict(_WORKOUT_DEFINITIONS_CORE)

# -----------------------------------------------------------------------------
# PLACEMENT_ROLE_TYPES — roles for scheduling / mileage distribution (not taxonomy)
# Aligned with ``src.services.training_plan.workout_types`` role keys.
# -----------------------------------------------------------------------------

PLACEMENT_ROLE_TYPES: FrozenSet[str] = frozenset(
    [
        "easy",
        "steady",
        "endurance",
        "long",
    ]
)

# -----------------------------------------------------------------------------
# ROLE_TO_TAXONOMY_MAP — scheduling role → workout taxonomy (interpretation only)
# -----------------------------------------------------------------------------
# Maps placement roles used in scheduling to default taxonomy keys. Use for
# interpretation (insights, coach); plan generation logic may still apply
# additional rules. This does not replace Pass3–Pass7 behavior.

ROLE_TO_TAXONOMY_MAP: Dict[str, str] = {
    "long": "long_run",
    "endurance": "easy",
    "steady": "steady",
    "easy": "easy",
}

# -----------------------------------------------------------------------------
# Basic constraints (aligned with documented V2 definition invariants)
# -----------------------------------------------------------------------------

RUNNING_RULES: Dict[str, Any] = {
    "allowed_intensity_labels": frozenset(
        {"very_easy", "easy", "moderate", "hard", "very_hard"}
    ),
    "quality_session_min_recovery_days_after": 2,
    "weekly_long_run_taxonomy_key": "long_run",
    "placement_role_keys": PLACEMENT_ROLE_TYPES,
}

# -----------------------------------------------------------------------------
# Heart-rate / effort zones — placeholders for a future unified zone model
# (Z1–Z5). Names are generic; wire to pace or HR bands in a later phase.
# -----------------------------------------------------------------------------

ZONE_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "Z1": {
        "label": "Zone 1",
        "typical_effort": "Recovery / very easy",
        "notes": "Placeholder; align with future HR or pace calibration.",
    },
    "Z2": {
        "label": "Zone 2",
        "typical_effort": "Easy aerobic",
        "notes": "Placeholder; align with future HR or pace calibration.",
    },
    "Z3": {
        "label": "Zone 3",
        "typical_effort": "Tempo / moderate hard",
        "notes": "Placeholder; align with future HR or pace calibration.",
    },
    "Z4": {
        "label": "Zone 4",
        "typical_effort": "Threshold / hard",
        "notes": "Placeholder; align with future HR or pace calibration.",
    },
    "Z5": {
        "label": "Zone 5",
        "typical_effort": "VO2max / neuromuscular",
        "notes": "Placeholder; align with future HR or pace calibration.",
    },
}


def get_taxonomy_for_role(role: str) -> str | None:
    """Return the default taxonomy key for ``role``, or ``None`` if unmapped."""
    return ROLE_TO_TAXONOMY_MAP.get(role)
