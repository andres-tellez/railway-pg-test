"""
Pass 4: Workout Details Service (Spec-Compliant)

Purpose:
    Generate detailed workout segments, pace guidance, and cues for each run.
    Creates spec-compliant segments with numeric targets (device-ready format).

Integration:
    Called after Pass 3 (workout distribution) to add detailed segments.
    Uses runner-profile pace zones to determine pace targets.

Unit Invariant:
    All pace targets are in seconds per mile (sec/mi) as integers.
    If/when km support is added, convert centrally in this module.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import Dict, Any, List, Optional
from datetime import date, datetime
import logging

from src.smartcoach_mobile_coach.runner_profile import (
    get_detail_archetype,
    placement_wu_cd_mi,
)
from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneComputation
from src.services.training_plan.v2.shared_v2.workout_detail_rules import (
    PHASE,
    STRIDES,
    MARATHON_FINISH,
    QUALITY_ENABLED_PHASES,
    DEFAULT_UNITS,
    THRESHOLD_INTERVALS,
    TEMPO_BLOCKS,
    is_peak_like_phase,
)
from src.services.training_plan.v2.shared_v2.workout_utils import pace_range_to_str

logger = logging.getLogger(__name__)

# Segment generator archetypes Pass4 understands (detail_archetype from taxonomy).
ARCHETYPE_EASY = "EASY"
ARCHETYPE_STEADY = "STEADY"
ARCHETYPE_ENDURANCE = "ENDURANCE"
ARCHETYPE_LONG = "LONG"
ARCHETYPE_TEMPO = "TEMPO"
ARCHETYPE_INTERVALS = "INTERVALS"
ARCHETYPE_HILLS = "HILLS"

# Taxonomy / placement type keys used in segment routing.
EASY = "easy"
STEADY = "steady"
ENDURANCE = "endurance"
LONG = "long_run"


# ---------- Helper Functions ----------


def _sec(s: float) -> int:
    """Convert seconds (float) to integer seconds."""
    return int(round(s))


def _fmt_range_dict(min_sec: float, max_sec: float) -> dict:
    """Format pace range as dict with low/high in seconds."""
    return {"low": _sec(min_sec), "high": _sec(max_sec)}


def _pace_labels(pace_zones: PaceZoneComputation) -> Dict[str, str]:
    """Canonical pace labels keyed by runner-profile zones (z2, z3, m, z4)."""
    z2 = pace_range_to_str(
        pace_zones.pace_z2.low_sec,
        pace_zones.pace_z2.high_sec,
    )
    z3 = pace_range_to_str(
        pace_zones.pace_z3.low_sec,
        pace_zones.pace_z3.high_sec,
    )
    m = pace_range_to_str(pace_zones.marathon_sec, pace_zones.marathon_sec)
    z4 = pace_range_to_str(
        pace_zones.pace_z4.low_sec,
        pace_zones.pace_z4.high_sec,
    )
    return {
        "z2": z2,
        "z3": z3,
        "m": m,
        "z4": z4,
    }


def _z2_low(pace_zones: PaceZoneComputation) -> int:
    return int(pace_zones.pace_z2.low_sec)


def _z2_high(pace_zones: PaceZoneComputation) -> int:
    return int(pace_zones.pace_z2.high_sec)


def _z3_low(pace_zones: PaceZoneComputation) -> int:
    return int(pace_zones.pace_z3.low_sec)


def _z3_high(pace_zones: PaceZoneComputation) -> int:
    return int(pace_zones.pace_z3.high_sec)


def _z4_low(pace_zones: PaceZoneComputation) -> int:
    return int(pace_zones.pace_z4.low_sec)


def _z4_high(pace_zones: PaceZoneComputation) -> int:
    return int(pace_zones.pace_z4.high_sec)


def _m_pace(pace_zones: PaceZoneComputation) -> int:
    return int(pace_zones.marathon_sec)


# _fmt_range_str removed - now using pace_range_to_str from workout_utils


def _wu_step(mi: float, easy_min: float, easy_max: float) -> dict:
    """Create warm-up step."""
    return {
        "name": "Warm-up",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(easy_min, easy_max),
        "intensity": "EASY",
    }


def _cd_step(mi: float, easy_min: float, easy_max: float) -> dict:
    """Create cool-down step."""
    return {
        "name": "Cool-down",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(easy_min, easy_max),
        "intensity": "EASY",
    }


def _rest_step(mi: float, easy_min: float, easy_max: float) -> dict:
    """Create rest/recovery step between intervals."""
    return {
        "name": "Rest",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(easy_min, easy_max),
        "intensity": "EASY",
    }


def _interval_step(
    interval_num: int, mi: float, threshold_min: float, threshold_max: float
) -> dict:
    """Create threshold interval step."""
    return {
        "name": f"Interval {interval_num}",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(threshold_min, threshold_max),
        "intensity": "THRESHOLD",
    }


def _tempo_block_step(
    block_num: int, mi: float, steady_min: float, steady_max: float
) -> dict:
    """Create tempo block step."""
    return {
        "name": f"Tempo Block {block_num}",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(steady_min, steady_max),
        "intensity": "STEADY",
    }


# =============================================================================
# SEGMENT VALIDATION HELPER
# =============================================================================


def _validate_and_adjust_segments(
    steps: List[dict],
    target_miles: float,
    pace_zones: PaceZoneComputation,
) -> List[dict]:
    """
    Validate that segment total matches target miles and adjust if needed.

    This ensures:
    - Total segment miles = target workout miles (within tolerance)
    - No negative or zero segments
    - Rounding errors are corrected

    Args:
        steps: List of segment dicts with 'value' field (miles)
        target_miles: Expected total workout distance
        pace_zones: runner-profile pace zones for creating adjustment segments

    Returns:
        Adjusted list of segments
    """
    if not steps:
        return steps

    # Filter out zero/negative segments first
    steps = [s for s in steps if s.get("value", 0) > 0]

    if not steps:
        return steps

    # Calculate current total
    total_segment_miles = sum(s.get("value", 0) for s in steps)
    diff = target_miles - total_segment_miles

    # Tolerance: 0.5 miles (acceptable rounding variance)
    TOLERANCE = 0.5

    if abs(diff) <= TOLERANCE:
        return steps

    # Need to adjust
    if diff > 0:
        # Under target: add easy miles to last non-cooldown segment or create new
        # Find the main segment (not warm-up or cool-down)
        for i in range(len(steps) - 1, -1, -1):
            name = steps[i].get("name", "").lower()
            if "cool" not in name and "warm" not in name:
                steps[i]["value"] = round(steps[i]["value"] + diff, 1)
                break
        else:
            # No main segment found, add to last segment
            steps[-1]["value"] = round(steps[-1]["value"] + diff, 1)
    else:
        # Over target: reduce from largest non-WU/CD segment
        abs_diff = abs(diff)
        for i in range(len(steps) - 1, -1, -1):
            name = steps[i].get("name", "").lower()
            if "cool" not in name and "warm" not in name:
                current = steps[i].get("value", 0)
                reduction = min(abs_diff, current - 0.5)  # Don't reduce below 0.5
                if reduction > 0:
                    steps[i]["value"] = round(current - reduction, 1)
                    abs_diff -= reduction
                if abs_diff <= 0:
                    break

    # Final filter for any zeros created
    steps = [s for s in steps if s.get("value", 0) > 0]

    return steps


# =============================================================================
# NEW ARCHETYPE GENERATORS - For new workout taxonomy types
# =============================================================================


def _detail_easy_fallback(
    distance_mi: float,
    pace_zones: PaceZoneComputation,
    cue_text: str,
) -> Dict[str, Any]:
    """
    Generate a simple easy run as fallback when hard workouts are inappropriate.

    Used when:
    - Hills requested during Taper
    - Intervals requested during cutback
    - Workout distance too short for hard effort

    Args:
        distance_mi: Total workout distance
        pace_zones: runner-profile pace zones
        cue_text: Custom cue explaining the downgrade

    Returns:
        Dict with segments, cues, pace_labels, quality_insert
    """
    steps = [
        {
            "name": "Easy Run",
            "durationType": "DISTANCE",
            "value": distance_mi,
            "target": _fmt_range_dict(_z2_low(pace_zones), _z2_high(pace_zones)),
            "intensity": "EASY",
        }
    ]

    return {
        "segments": {
            "units": DEFAULT_UNITS,
            "targetType": "PACE",
            "steps": steps,
            "notes": cue_text,
        },
        "cues": cue_text,
        "pace_labels": _pace_labels(pace_zones),
        "quality_insert": None,
    }


def _detail_tempo(
    distance_mi: float,
    phase: str,
    pace_zones: PaceZoneComputation,
    allow_quality: bool,
) -> Dict[str, Any]:
    """
    Generate detailed segments for TEMPO archetype.

    Structure: warm-up → continuous tempo block → cool-down

    PHASE-AWARE tempo duration caps (coaching best practice):
    - Base: 1.5-2.0 mi (~12-16 min) - building aerobic foundation
    - Build: 2.5-3.5 mi (~20-28 min) - extending threshold work
    - Peak: 3.5-4.5 mi (~28-36 min) - race-specific preparation
    - Taper: 1.0-1.5 mi (~8-12 min) - maintain sharpness, reduce volume

    Args:
        distance_mi: Total workout distance
        phase: Training phase
        pace_zones: runner-profile pace zones
        allow_quality: Whether quality elements are allowed

    Returns:
        Dict with segments, cues, pace_labels, quality_insert
    """
    steps = []
    cues = []
    quality_insert = None

    # Standard WU/CD
    wu_mi = 1.0
    cd_mi = 1.0

    # Calculate tempo portion based on total distance
    available_for_tempo = max(0.0, distance_mi - wu_mi - cd_mi)

    # =========================================================================
    # PHASE-AWARE TEMPO CAPS (coaching best practice)
    # =========================================================================
    # Base phase: Keep tempo short, focus on aerobic development
    # Build phase: Extend tempo duration progressively
    # Peak phase: Longest tempo blocks for race-specific fitness
    # Taper phase: Short, sharp tempo to maintain leg speed

    if phase == "Base":
        max_tempo_mi = 2.0  # ~16 min max
    elif phase == "Build":
        max_tempo_mi = 3.5  # ~28 min max
    elif is_peak_like_phase(phase):
        max_tempo_mi = 4.5  # ~36 min max
    elif phase == "Taper":
        max_tempo_mi = 1.5  # ~12 min max - maintain sharpness only
    else:
        max_tempo_mi = 3.0  # Default

    # Calculate tempo miles within phase cap
    tempo_mi = min(available_for_tempo, max_tempo_mi)

    # Any remaining goes to easy running
    easy_mi = max(0.0, available_for_tempo - tempo_mi)

    # Build steps
    steps.append(_wu_step(wu_mi, _z2_low(pace_zones), _z2_high(pace_zones)))

    if tempo_mi > 0:
        steps.append(
            {
                "name": "Tempo",
                "durationType": "DISTANCE",
                "value": tempo_mi,
                "target": _fmt_range_dict(_z4_low(pace_zones), _z4_high(pace_zones)),
                "intensity": "TEMPO",
            }
        )
        quality_insert = {"type": "tempo", "miles": tempo_mi, "phase": phase}

    if easy_mi > 0.5:
        steps.append(
            {
                "name": "Easy",
                "durationType": "DISTANCE",
                "value": easy_mi,
                "target": _fmt_range_dict(_z2_low(pace_zones), _z2_high(pace_zones)),
                "intensity": "EASY",
            }
        )

    steps.append(_cd_step(cd_mi, _z2_low(pace_zones), _z2_high(pace_zones)))

    # Phase-specific cues
    if phase == "Base":
        cues.append(
            f"Tempo run: {tempo_mi:.1f} mi at comfortably hard pace. "
            "Keep it controlled - we're building your aerobic foundation."
        )
    elif phase == "Taper":
        cues.append(
            f"Short tempo: {tempo_mi:.1f} mi to keep legs sharp. "
            "Don't push too hard - save energy for race day."
        )
    else:
        cues.append(
            f"Tempo run: {tempo_mi:.1f} mi at comfortably hard pace. "
            "You should be able to speak in short phrases but not hold a conversation."
        )
        if is_peak_like_phase(phase):
            cues.append(
                "This is race-specific work. Focus on maintaining consistent effort."
            )

    # Validate and adjust segment totals
    steps = _validate_and_adjust_segments(steps, distance_mi, pace_zones)

    cues_str = " ".join(cues)
    return {
        "segments": {
            "units": DEFAULT_UNITS,
            "targetType": "PACE",
            "steps": steps,
            "notes": cues_str,
        },
        "cues": cues_str,
        "pace_labels": _pace_labels(pace_zones),
        "quality_insert": quality_insert,
    }


def _detail_intervals(
    distance_mi: float,
    phase: str,
    pace_zones: PaceZoneComputation,
    allow_quality: bool,
) -> Dict[str, Any]:
    """
    Generate detailed segments for INTERVALS archetype.

    Structure: warm-up → repeats with recovery → cool-down

    Interval structure scales with total distance:
    - Short (< 6 mi): 4 × 0.5 mi (800m) with 0.25 mi recovery
    - Medium (6-8 mi): 5 × 0.75 mi (1200m) with 0.25 mi recovery
    - Long (> 8 mi): 6 × 1.0 mi with 0.25 mi recovery

    Args:
        distance_mi: Total workout distance
        phase: Training phase
        pace_zones: runner-profile pace zones
        allow_quality: Whether quality elements are allowed

    Returns:
        Dict with segments, cues, pace_labels, quality_insert
    """
    steps = []
    cues = []
    quality_insert = None

    # Standard WU/CD (slightly longer for intervals)
    wu_mi = 1.5
    cd_mi = 1.0
    recovery_mi = 0.25  # Recovery jog between intervals

    # Determine interval structure based on distance
    if distance_mi < 6.0:
        reps = 4
        interval_mi = 0.5  # ~800m
    elif distance_mi < 8.0:
        reps = 5
        interval_mi = 0.75  # ~1200m
    else:
        reps = 6
        interval_mi = 1.0  # 1 mile

    # Build steps
    steps.append(_wu_step(wu_mi, _z2_low(pace_zones), _z2_high(pace_zones)))

    total_interval_mi = 0.0
    for i in range(1, reps + 1):
        # Interval step
        steps.append(
            {
                "name": f"Interval {i}",
                "durationType": "DISTANCE",
                "value": interval_mi,
                "target": _fmt_range_dict(
                    _z4_low(pace_zones) - 15, _z4_low(pace_zones)
                ),  # Slightly faster than T
                "intensity": "INTERVAL",
            }
        )
        total_interval_mi += interval_mi

        # Recovery (not after last interval)
        if i < reps:
            steps.append(
                {
                    "name": "Recovery",
                    "durationType": "DISTANCE",
                    "value": recovery_mi,
                    "target": _fmt_range_dict(
                        _z2_low(pace_zones), _z2_high(pace_zones)
                    ),
                    "intensity": "RECOVERY",
                }
            )

    steps.append(_cd_step(cd_mi, _z2_low(pace_zones), _z2_high(pace_zones)))

    quality_insert = {"type": "intervals", "reps": reps, "interval_mi": interval_mi}

    cues.append(
        f"Interval workout: {reps} × {interval_mi:.2f} mi at hard effort "
        f"with {recovery_mi:.2f} mi easy jog recovery between."
    )
    cues.append("Run intervals at a controlled hard effort - fast but sustainable.")

    if is_peak_like_phase(phase):
        cues.append("These are race-sharpening intervals. Stay relaxed and powerful.")

    # Validate and adjust segment totals
    steps = _validate_and_adjust_segments(steps, distance_mi, pace_zones)

    cues_str = " ".join(cues)
    return {
        "segments": {
            "units": DEFAULT_UNITS,
            "targetType": "PACE",
            "steps": steps,
            "notes": cues_str,
        },
        "cues": cues_str,
        "pace_labels": _pace_labels(pace_zones),
        "quality_insert": quality_insert,
    }


def _detail_hills(
    distance_mi: float,
    phase: str,
    pace_zones: PaceZoneComputation,
    allow_quality: bool,
) -> Dict[str, Any]:
    """
    Generate detailed segments for HILLS archetype.

    Structure: warm-up → hill repeats with jog down → cool-down

    PHASE-RESTRICTED (coaching best practice):
    - Base: Moderate hills (6-8 reps) - building strength foundation
    - Build: Full hills (8-10 reps) - peak hill training
    - Peak: Reduced hills (4-6 reps) - maintain, don't build
    - Taper: NO HILLS - downgrade to easy run

    Args:
        distance_mi: Total workout distance
        phase: Training phase
        pace_zones: runner-profile pace zones
        allow_quality: Whether quality elements are allowed

    Returns:
        Dict with segments, cues, pace_labels, quality_insert
    """
    # =========================================================================
    # PHASE RESTRICTION: No hills in Taper - too much stress
    # =========================================================================
    if phase == "Taper":
        # Downgrade to easy run - hills are unsafe during taper
        return _detail_easy_fallback(
            distance_mi,
            pace_zones,
            "Easy run (hills removed for taper). Keep legs fresh for race day.",
        )

    steps = []
    cues = []
    quality_insert = None

    wu_mi = 1.5
    cd_mi = 1.0

    # =========================================================================
    # PHASE-AWARE REP COUNTS (coaching best practice)
    # =========================================================================
    # Base: Building strength foundation - moderate volume
    # Build: Peak hill training - highest volume
    # Peak: Maintain strength - reduced volume

    if phase == "Base":
        # Moderate hills in Base - building foundation
        if distance_mi < 5.0:
            reps = 5
        elif distance_mi < 7.0:
            reps = 6
        else:
            reps = 7
    elif phase == "Build":
        # Full hills in Build - peak training
        if distance_mi < 5.0:
            reps = 6
        elif distance_mi < 7.0:
            reps = 8
        else:
            reps = 10
    elif is_peak_like_phase(phase):
        # Reduced hills in Peak - maintain, don't build
        if distance_mi < 5.0:
            reps = 4
        elif distance_mi < 7.0:
            reps = 5
        else:
            reps = 6
    else:
        # Default
        reps = 6

    hill_mi = 0.15  # ~60-90 seconds uphill
    recovery_mi = 0.15  # Jog down

    steps.append(_wu_step(wu_mi, _z2_low(pace_zones), _z2_high(pace_zones)))

    for i in range(1, reps + 1):
        steps.append(
            {
                "name": f"Hill {i}",
                "durationType": "DISTANCE",
                "value": hill_mi,
                "target": _fmt_range_dict(
                    _z4_low(pace_zones) - 30, _z4_low(pace_zones)
                ),  # Hard effort
                "intensity": "HARD",
            }
        )
        if i < reps:
            steps.append(
                {
                    "name": "Jog Down",
                    "durationType": "DISTANCE",
                    "value": recovery_mi,
                    "target": _fmt_range_dict(
                        _z2_low(pace_zones) + 30, _z2_high(pace_zones) + 30
                    ),  # Very easy
                    "intensity": "RECOVERY",
                }
            )

    steps.append(_cd_step(cd_mi, _z2_low(pace_zones), _z2_high(pace_zones)))

    quality_insert = {"type": "hills", "reps": reps, "phase": phase}

    # Phase-specific cues
    if phase == "Base":
        cues.append(
            f"Hill workout: {reps} × ~60-90 second hill repeats. "
            "Focus on building strength - don't go all-out."
        )
    elif is_peak_like_phase(phase):
        cues.append(
            f"Maintenance hills: {reps} × ~60-90 second repeats. "
            "Keep intensity moderate - we're maintaining, not building."
        )
    else:
        cues.append(
            f"Hill workout: {reps} × ~60-90 second hill repeats at hard effort. "
            "Jog easily back down for recovery."
        )

    cues.append("Focus on driving knees and pumping arms. Stay relaxed in shoulders.")

    # Validate and adjust segment totals
    steps = _validate_and_adjust_segments(steps, distance_mi, pace_zones)

    cues_str = " ".join(cues)
    return {
        "segments": {
            "units": DEFAULT_UNITS,
            "targetType": "PACE",
            "steps": steps,
            "notes": cues_str,
        },
        "cues": cues_str,
        "pace_labels": _pace_labels(pace_zones),
        "quality_insert": quality_insert,
    }


# =============================================================================
# MAIN DETAIL GENERATOR - Archetype-based dispatch
# =============================================================================


def _detail_run(
    run_type: str,
    distance_mi: float,
    phase: str,
    pace_zones: PaceZoneComputation,
    allow_quality: bool,
    is_cutback: bool = False,
) -> Dict[str, Any]:
    """
    Generate detailed segments and cues (spec-compliant).

    Uses archetype-based dispatch to route workout types to appropriate generators.
    New workout types from the taxonomy are mapped via detail_archetype field.

    SAFETY FEATURES:
    - Minimum distance check: Hard workouts < 4 mi are downgraded to easy
    - Cutback enforcement: No hard workouts during cutback weeks
    - Phase restrictions: Handled by individual generators

    Args:
        run_type: Workout type from taxonomy (e.g., "easy", "tempo", "intervals")
        distance_mi: Total distance in miles
        phase: Training phase (Base, Build, Peak, Taper)
        pace_zones: runner-profile pace zones
        allow_quality: Whether to allow quality elements (T-block, M-finish)
        is_cutback: Whether this is a cutback/recovery week

    Returns:
        Dict with:
            - segments: Spec-compliant segments object with units/targetType/steps/notes
            - cues: String with workout cues/guidance
            - pace_labels: Dict of pace labels (z2, z3, m, z4) for display
            - quality_insert: Optional quality insert metadata
    """
    # =========================================================================
    # ARCHETYPE-BASED DISPATCH
    # =========================================================================
    # Get the detail archetype from the taxonomy (or default based on run_type)
    archetype = get_detail_archetype(run_type)

    # =========================================================================
    # SAFETY CHECK #1: Minimum distance for hard workouts
    # =========================================================================
    # Hard workouts need room for warm-up, main set, and cool-down
    # Workouts < 4 miles cannot safely accommodate hard efforts
    MIN_HARD_WORKOUT_MILES = 4.0
    HARD_ARCHETYPES = {ARCHETYPE_TEMPO, ARCHETYPE_INTERVALS, ARCHETYPE_HILLS}

    if archetype in HARD_ARCHETYPES and distance_mi < MIN_HARD_WORKOUT_MILES:
        return _detail_easy_fallback(
            distance_mi,
            pace_zones,
            f"Easy run (workout too short for {run_type}). "
            f"Hard workouts need at least {MIN_HARD_WORKOUT_MILES} miles for safe structure.",
        )

    # =========================================================================
    # SAFETY CHECK #2: No hard workouts during cutback weeks
    # =========================================================================
    # Cutback weeks are for recovery - Step 6 should have already downgraded,
    # but we enforce it here as a safety net
    if is_cutback and archetype in HARD_ARCHETYPES:
        return _detail_easy_fallback(
            distance_mi,
            pace_zones,
            "Easy recovery run (cutback week). Focus on rest and recovery.",
        )

    # =========================================================================
    # ROUTE TO APPROPRIATE GENERATOR
    # =========================================================================
    if archetype == ARCHETYPE_TEMPO:
        return _detail_tempo(distance_mi, phase, pace_zones, allow_quality)

    if archetype == ARCHETYPE_INTERVALS:
        return _detail_intervals(distance_mi, phase, pace_zones, allow_quality)

    if archetype == ARCHETYPE_HILLS:
        return _detail_hills(distance_mi, phase, pace_zones, allow_quality)

    # =========================================================================
    # LEGACY GENERATORS - For EASY, STEADY, ENDURANCE, LONG
    # =========================================================================
    steps = []
    cues = []
    quality_insert = None

    # Get WU/CD distances from config
    wu_cd = placement_wu_cd_mi(run_type)
    wu_mi = wu_cd["wu"]
    cd_mi = wu_cd["cd"]

    # Map archetype back to legacy constants for existing logic
    if archetype == ARCHETYPE_EASY or run_type == EASY:
        # Simple easy run — no WU/CD needed (matches training science best practice)
        # Easy runs are low-stress throughout; WU/CD only needed for hard workouts
        steps = [
            {
                "name": "Easy",
                "durationType": "DISTANCE",
                "value": distance_mi,  # Use full distance (no WU/CD subtraction)
                "target": _fmt_range_dict(_z2_low(pace_zones), _z2_high(pace_zones)),
                "intensity": "EASY",
            }
        ]
        cues.append("Conversational effort; keep it relaxed.")

        # Optional strides rule preserved
        if (
            allow_quality
            and phase in STRIDES["enabled_phases"]
            and distance_mi >= STRIDES["min_run_mi"]
        ):
            cues.append(
                f"Optional: {STRIDES['reps']}×{STRIDES['on_sec']}s relaxed strides "
                f"with {STRIDES['off_sec']}s easy jog."
            )

    elif archetype == ARCHETYPE_STEADY or run_type == STEADY:
        # Generate interval workouts for STEADY in Build/Peak phases
        if (
            allow_quality
            and phase in THRESHOLD_INTERVALS["enabled_phases"]
            and distance_mi >= THRESHOLD_INTERVALS["min_run_mi"]
        ):
            # Determine interval type based on total distance
            if distance_mi < 7.0:
                interval_config = THRESHOLD_INTERVALS["interval_types"]["short"]
            elif distance_mi < 9.0:
                interval_config = THRESHOLD_INTERVALS["interval_types"]["medium"]
            else:
                interval_config = THRESHOLD_INTERVALS["interval_types"]["long"]

            # Calculate total interval distance
            total_interval_mi = interval_config["reps"] * interval_config["interval_mi"]
            # Rest only between intervals (not after last), so (reps - 1) rests
            total_rest_mi = (interval_config["reps"] - 1) * interval_config["rest_mi"]
            remaining_mi = max(
                0.0, distance_mi - (wu_mi + total_interval_mi + total_rest_mi + cd_mi)
            )

            # Build steps: warm-up, intervals with rest, cooldown
            steps = [_wu_step(wu_mi, _z2_low(pace_zones), _z2_high(pace_zones))]

            # Add intervals with rest between
            for i in range(1, interval_config["reps"] + 1):
                steps.append(
                    _interval_step(
                        i,
                        interval_config["interval_mi"],
                        _z4_low(pace_zones),
                        _z4_high(pace_zones),
                    )
                )
                if (
                    i < interval_config["reps"]
                ):  # Rest between intervals (not after last)
                    steps.append(
                        _rest_step(
                            interval_config["rest_mi"],
                            _z2_low(pace_zones),
                            _z2_high(pace_zones),
                        )
                    )

            # Add any remaining steady distance if needed
            if remaining_mi > 0.1:
                steps.append(
                    {
                        "name": "Steady",
                        "durationType": "DISTANCE",
                        "value": remaining_mi,
                        "target": _fmt_range_dict(
                            _z3_low(pace_zones), _z3_high(pace_zones)
                        ),
                        "intensity": "STEADY",
                    }
                )

            steps.append(_cd_step(cd_mi, _z2_low(pace_zones), _z2_high(pace_zones)))

            cues.append(
                f"Threshold intervals: {interval_config['reps']}×{interval_config['interval_mi']:.2f}mi "
                f"at threshold pace with {interval_config['rest_mi']:.2f}mi easy recovery."
            )
        else:
            # Continuous steady run (Base phase or when quality not allowed)
            main_mi = max(0.0, distance_mi - (wu_mi + cd_mi))
            steps = [
                _wu_step(wu_mi, _z2_low(pace_zones), _z2_high(pace_zones)),
                {
                    "name": "Steady",
                    "durationType": "DISTANCE",
                    "value": main_mi,
                    "target": _fmt_range_dict(
                        _z3_low(pace_zones), _z3_high(pace_zones)
                    ),
                    "intensity": "STEADY",
                },
                _cd_step(cd_mi, _z2_low(pace_zones), _z2_high(pace_zones)),
            ]
            cues.append("Controlled effort; steady, not hard.")

            if (
                allow_quality
                and phase in STRIDES["enabled_phases"]
                and distance_mi >= STRIDES["min_run_mi"]
            ):
                cues.append(
                    f"Optional: add {STRIDES['reps']}×{STRIDES['on_sec']}s strides mid-run "
                    f"({STRIDES['off_sec']}s easy between)."
                )

    elif archetype == ARCHETYPE_ENDURANCE or run_type == ENDURANCE:
        main_mi = max(0.0, distance_mi - (wu_mi + cd_mi))
        steps = [
            _wu_step(wu_mi, _z2_low(pace_zones), _z2_high(pace_zones)),
            {
                "name": "Endurance",
                "durationType": "DISTANCE",
                "value": main_mi,
                "target": _fmt_range_dict(_z3_low(pace_zones), _z3_high(pace_zones)),
                "intensity": "STEADY",
            },
            _cd_step(cd_mi, _z2_low(pace_zones), _z2_high(pace_zones)),
        ]
        cues.append("Medium-long run; builds fatigue tolerance.")

        if allow_quality and is_peak_like_phase(phase) and main_mi >= 6.0:
            cues.append("If feeling good: last 2–3 mi at marathon pace.")

    elif archetype == ARCHETYPE_LONG or run_type == LONG:
        # Check marathon finish conditions from config
        m_finish_enabled = (
            phase in MARATHON_FINISH["enabled_phases"]
            and allow_quality
            and distance_mi >= MARATHON_FINISH["min_lr_mi"]
        )

        # Phase-aware Long run pace:
        # - Base: Easy pace (E)
        # - Build: Steady pace (S) - slightly faster than Easy
        # - Peak: Easy pace (E) + optional M-finish segments
        # - Taper: Easy pace (E)
        use_steady_pace = phase == PHASE["BUILD"] and not m_finish_enabled
        long_pace_min = _z3_low(pace_zones) if use_steady_pace else _z2_low(pace_zones)
        long_pace_max = (
            _z3_high(pace_zones) if use_steady_pace else _z2_high(pace_zones)
        )
        long_intensity = "STEADY" if use_steady_pace else "EASY"
        long_name = "Long Steady" if use_steady_pace else "Long Easy"

        if m_finish_enabled:
            # Fix rounding to avoid drift
            finish_raw = distance_mi * MARATHON_FINISH["finish_fraction"]
            finish_mi = max(MARATHON_FINISH["min_finish_mi"], round(finish_raw, 1))
            easy_part = round(distance_mi - finish_mi, 1)

            steps = [
                {
                    "name": "Long Easy",
                    "durationType": "DISTANCE",
                    "value": easy_part,
                    "target": _fmt_range_dict(
                        _z2_low(pace_zones), _z2_high(pace_zones)
                    ),
                    "intensity": "EASY",
                },
                {
                    "name": "Marathon finish",
                    "durationType": "DISTANCE",
                    "value": finish_mi,
                    "target": {
                        "low": _sec(_m_pace(pace_zones)),
                        "high": _sec(_m_pace(pace_zones)),
                    },
                    "intensity": "MARATHON",
                },
            ]
            cues.append(
                "Fuel 30–40g carbs every 30–40 min; sip fluids regularly. "
                f"Finish last {int(finish_mi)} mi at marathon pace if feeling strong."
            )
            quality_insert = {"type": "marathon_finish", "miles": finish_mi}
        else:
            steps = [
                {
                    "name": long_name,
                    "durationType": "DISTANCE",
                    "value": distance_mi,
                    "target": _fmt_range_dict(long_pace_min, long_pace_max),
                    "intensity": long_intensity,
                }
            ]
            if use_steady_pace:
                cues.append(
                    "Steady long run at moderate effort; practice fueling every 30–40 min. "
                    "Slightly faster than easy pace but still comfortable."
                )
            else:
                cues.append(
                    "Keep it easy; practice fueling every 30–40 min. "
                    "Conversational effort throughout."
                )
    else:
        # Fallback for unknown types
        steps = [
            {
                "name": "Run",
                "durationType": "DISTANCE",
                "value": distance_mi,
                "target": _fmt_range_dict(_z2_low(pace_zones), _z2_high(pace_zones)),
                "intensity": "EASY",
            }
        ]
        cues.append("Run at comfortable effort.")

    # ✅ Filter out zero/negative steps (prevent clutter and drift)
    steps = [s for s in steps if s.get("value", 0) > 0]

    # Build spec-compliant segments object
    cues_str = " ".join(cues)
    segments_obj = {
        "units": DEFAULT_UNITS,
        "targetType": "PACE",
        "steps": steps,
        "notes": cues_str,
    }

    return {
        "segments": segments_obj,
        "cues": cues_str,
        "pace_labels": _pace_labels(pace_zones),
        "quality_insert": quality_insert,
    }


class Pass4WorkoutDetails:
    """Service for adding detailed segments and pace guidance to workouts."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def add_details_to_plan(
        self,
        plan: Dict[str, Any],
        pace_zones: PaceZoneComputation,
        mode: str = "prefill",
        week_logs: Dict[int, List] = None,
    ) -> Dict[str, Any]:
        """
        Add detailed segments to all workouts in a plan.

        Args:
            plan: Plan dict with 'weeks' array (from Pass 3) and 'race_date'
            pace_zones: Initial runner-profile pace zones (adjusted per week in rolling mode)
            mode: "prefill" (all weeks) or "rolling" (current week only)
            week_logs: Optional dict mapping week_num -> List[WeekLogRun] for adjustments

        Returns:
            Plan dict with detailed segments added to each workout

        Note:
            In "rolling" mode, only the week containing today's date is detailed.
            This is calculated based on race_date and today's date, not plan week_number 1.
        """
        if week_logs is None:
            week_logs = {}

        weeks = plan.get("weeks", [])
        if not weeks:
            self.logger.warning("Plan has no weeks - no details to add")
            return plan

        # In rolling mode, calculate which week number contains today
        current_week_num: Optional[int] = None
        if mode == "rolling":
            race_date = plan.get("race_date")
            if race_date:
                # Convert race_date to date object if it's a string
                if isinstance(race_date, str):
                    race_date = datetime.fromisoformat(race_date.split("T")[0]).date()
                elif isinstance(race_date, datetime):
                    race_date = race_date.date()

                # Calculate current week number (week containing today)
                today = date.today()
                from src.utils.date_helpers import get_week_start_for_date

                # Get Monday of current week (not next Monday)
                current_week_monday = get_week_start_for_date(today)

                # Calculate weeks until race from current week's Monday
                days_until_race = (race_date - current_week_monday).days

                # Calculate week number (weeks before race week)
                weeks_until_race = None
                if days_until_race >= 7:
                    weeks_until_race = days_until_race // 7
                    current_week_num = (
                        weeks_until_race if weeks_until_race > 0 else None
                    )

                # Convert to plan week_number (plan weeks are numbered 1-N, where N is furthest from race)
                # Plan week_number = max_week_num - weeks_before_race
                if current_week_num is not None:
                    max_week_num = max(w.get("week_number", 0) for w in weeks)
                    plan_week_num = max_week_num - current_week_num
                    current_week_num = plan_week_num if plan_week_num > 0 else None

                if current_week_num and weeks_until_race is not None:
                    self.logger.info(
                        f"Rolling mode: Current week is plan week_number={current_week_num} "
                        f"(week containing today, {weeks_until_race} weeks before race)"
                    )
                else:
                    self.logger.warning(
                        "Rolling mode: Could not determine current week number, "
                        "will detail all weeks (fallback to prefill behavior)"
                    )

        current_pace_zones = pace_zones
        adjusted_seed = False

        for week in weeks:
            week_num = week.get("week_number", 1)
            phase = week.get("phase", PHASE["BASE"])
            workouts = week.get("workouts", [])

            # In rolling mode, only detail the current week (week containing today)
            if mode == "rolling":
                if current_week_num is None:
                    # Fallback: if we couldn't determine current week, detail all weeks
                    pass
                elif week_num != current_week_num:
                    self.logger.debug(
                        f"Rolling mode: skipping details for week {week_num} "
                        f"(current week is {current_week_num})"
                    )
                    continue

            # Adjust pace zones based on previous week logs (rolling mode)
            if week_num > 1 and week_logs.get(week_num - 1):
                from .weekly_adjuster import adjust_pace_zones_from_week

                prev_week_log = week_logs[week_num - 1]
                current_pace_zones, disable_quality = adjust_pace_zones_from_week(
                    current_pace_zones, prev_week_log
                )
                adjusted_seed = True
                self.logger.info(
                    f"Week {week_num}: Adjusted pace zones from previous week logs "
                    f"(disable_quality={disable_quality})"
                )
            else:
                # Allow quality for Build/Peak phases
                disable_quality = False

            # Determine if quality elements are allowed (from config)
            allow_quality = (phase in QUALITY_ENABLED_PHASES) and not disable_quality

            # Check if this is a cutback week (from Step 6)
            is_cutback = week.get("is_cutback", False)

            # Store canonical zone-key metadata for downstream plan storage consumers.
            week["_pace_zones"] = {
                "z2": [_z2_low(current_pace_zones), _z2_high(current_pace_zones)],
                "z3": [_z3_low(current_pace_zones), _z3_high(current_pace_zones)],
                "z4": [_z4_low(current_pace_zones), _z4_high(current_pace_zones)],
                "m": [_m_pace(current_pace_zones), _m_pace(current_pace_zones)],
                "week1_long_cap": float(current_pace_zones.week1_long_cap),
            }

            # Add details to each workout in the week
            for workout in workouts:
                run_type = workout.get("type", EASY)
                distance_mi = float(
                    workout.get("miles", workout.get("distance_miles", 0)) or 0
                )

                if distance_mi <= 0:
                    self.logger.warning(
                        f"Week {week_num}: Skipping workout with 0 miles"
                    )
                    continue

                # Generate detailed segments (with cutback safety check)
                details = _detail_run(
                    run_type,
                    distance_mi,
                    phase,
                    current_pace_zones,
                    allow_quality,
                    is_cutback=is_cutback,
                )

                # Add details to workout
                workout["segments"] = details["segments"]
                workout["cues"] = details["cues"]
                workout["pace_labels"] = details["pace_labels"]
                workout["quality_insert"] = details["quality_insert"]

                # Count steps (after filtering)
                step_count = len(details["segments"].get("steps", []))
                self.logger.debug(
                    f"Week {week_num} {workout.get('day', 'Unknown')}: "
                    f"{run_type} {distance_mi:.1f}mi with {step_count} steps"
                )

        if adjusted_seed:
            self.logger.info("Pace zones adjusted based on week logs")

        return plan

    def add_details_to_week(
        self,
        week: Dict[str, Any],
        pace_zones: PaceZoneComputation,
        allow_quality: bool = False,
    ) -> Dict[str, Any]:
        """
        Add details to a single week (used for rolling updates).

        Args:
            week: Week dict with workouts
            pace_zones: Current runner-profile pace zones (may be adjusted)
            allow_quality: Whether quality elements are allowed

        Returns:
            Week dict with details added
        """
        phase = week.get("phase", PHASE["BASE"])
        workouts = week.get("workouts", [])
        is_cutback = week.get("is_cutback", False)

        # Store canonical zone-key metadata
        week["_pace_zones"] = {
            "z2": [_z2_low(pace_zones), _z2_high(pace_zones)],
            "z3": [_z3_low(pace_zones), _z3_high(pace_zones)],
            "z4": [_z4_low(pace_zones), _z4_high(pace_zones)],
            "m": [_m_pace(pace_zones), _m_pace(pace_zones)],
            "week1_long_cap": float(pace_zones.week1_long_cap),
        }

        for workout in workouts:
            run_type = workout.get("type", EASY)
            distance_mi = float(
                workout.get("miles", workout.get("distance_miles", 0)) or 0
            )

            if distance_mi <= 0:
                continue

            details = _detail_run(
                run_type,
                distance_mi,
                phase,
                pace_zones,
                allow_quality,
                is_cutback=is_cutback,
            )
            workout["segments"] = details["segments"]
            workout["cues"] = details["cues"]
            workout["pace_labels"] = details["pace_labels"]
            workout["quality_insert"] = details["quality_insert"]

        return week
