"""
Pass 4: Workout Details Service (Spec-Compliant)

Purpose:
    Generate detailed workout segments, pace guidance, and cues for each run.
    Creates spec-compliant segments with numeric targets (device-ready format).

Integration:
    Called after Pass 3 (workout distribution) to add detailed segments.
    Uses PaceSeed from pace_seed_service.py to determine pace zones.

Unit Invariant:
    All pace targets are in seconds per mile (sec/mi) as integers.
    If/when km support is added, convert centrally in this module.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import Dict, Any, List
import logging

from src.services.training_plan.v2.workout_taxonomy.workout_definitions import (
    WORKOUT_DEFINITIONS,
    get_workout_definition,
    get_detail_archetype,
)

# =============================================================================
# DETAIL ARCHETYPE CONSTANTS
# =============================================================================
# These are the segment generator archetypes that Pass4 understands.
# Each workout type from the taxonomy maps to one of these archetypes.

ARCHETYPE_EASY = "EASY"
ARCHETYPE_STEADY = "STEADY"
ARCHETYPE_ENDURANCE = "ENDURANCE"
ARCHETYPE_LONG = "LONG"
ARCHETYPE_TEMPO = "TEMPO"
ARCHETYPE_INTERVALS = "INTERVALS"
ARCHETYPE_HILLS = "HILLS"

# Legacy workout type constants (for backward compatibility with existing code)
EASY = "easy"
STEADY = "steady"
ENDURANCE = "endurance"
LONG = "long_run"

# Build TYPE_DISPLAY from taxonomy
TYPE_DISPLAY = {
    EASY: WORKOUT_DEFINITIONS["easy"]["description"],
    STEADY: WORKOUT_DEFINITIONS["steady"]["description"],
    ENDURANCE: "Endurance (Medium-Long)",  # Keep legacy display name
    LONG: WORKOUT_DEFINITIONS["long_run"]["description"],
}
from src.services.training_plan.v2.shared_v2.pace_seed_service import PaceSeed
from src.services.training_plan.v2.shared_v2.workout_detail_rules import (
    PHASE,
    WU_CD_MI,
    STRIDES,
    MARATHON_FINISH,
    QUALITY_ENABLED_PHASES,
    DEFAULT_UNITS,
    THRESHOLD_INTERVALS,
    TEMPO_BLOCKS,
)
from src.services.training_plan.v2.shared_v2.workout_utils import pace_range_to_str

logger = logging.getLogger(__name__)


# ---------- Helper Functions ----------


def _sec(s: float) -> int:
    """Convert seconds (float) to integer seconds."""
    return int(round(s))


def _fmt_range_dict(min_sec: float, max_sec: float) -> dict:
    """Format pace range as dict with low/high in seconds."""
    return {"low": _sec(min_sec), "high": _sec(max_sec)}


# _fmt_range_str removed - now using pace_range_to_str from workout_utils


def _wu_step(mi: float, E_min: float, E_max: float) -> dict:
    """Create warm-up step."""
    return {
        "name": "Warm-up",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(E_min, E_max),
        "intensity": "EASY",
    }


def _cd_step(mi: float, E_min: float, E_max: float) -> dict:
    """Create cool-down step."""
    return {
        "name": "Cool-down",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(E_min, E_max),
        "intensity": "EASY",
    }


def _rest_step(mi: float, E_min: float, E_max: float) -> dict:
    """Create rest/recovery step between intervals."""
    return {
        "name": "Rest",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(E_min, E_max),
        "intensity": "EASY",
    }


def _interval_step(interval_num: int, mi: float, T_min: float, T_max: float) -> dict:
    """Create threshold interval step."""
    return {
        "name": f"Interval {interval_num}",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(T_min, T_max),
        "intensity": "THRESHOLD",
    }


def _tempo_block_step(block_num: int, mi: float, S_min: float, S_max: float) -> dict:
    """Create tempo block step."""
    return {
        "name": f"Tempo Block {block_num}",
        "durationType": "DISTANCE",
        "value": mi,
        "target": _fmt_range_dict(S_min, S_max),
        "intensity": "STEADY",
    }


# =============================================================================
# SEGMENT VALIDATION HELPER
# =============================================================================

def _validate_and_adjust_segments(
    steps: List[dict],
    target_miles: float,
    seed: PaceSeed,
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
        seed: PaceSeed for creating adjustment segments
        
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
    seed: PaceSeed,
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
        seed: PaceSeed with pace zones
        cue_text: Custom cue explaining the downgrade
        
    Returns:
        Dict with segments, cues, pace_labels, quality_insert
    """
    steps = [
        {
            "name": "Easy Run",
            "durationType": "DISTANCE",
            "value": distance_mi,
            "target": _fmt_range_dict(seed.E_min, seed.E_max),
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
        "pace_labels": {
            "E": pace_range_to_str(seed.E_min, seed.E_max),
            "S": pace_range_to_str(seed.S_min, seed.S_max),
            "M": pace_range_to_str(seed.M, seed.M),
            "T": pace_range_to_str(seed.T_min, seed.T_max),
        },
        "quality_insert": None,
    }


def _detail_tempo(
    distance_mi: float,
    phase: str,
    seed: PaceSeed,
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
        seed: PaceSeed with pace zones
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
    elif phase == "Peak":
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
    steps.append(_wu_step(wu_mi, seed.E_min, seed.E_max))
    
    if tempo_mi > 0:
        steps.append({
            "name": "Tempo",
            "durationType": "DISTANCE",
            "value": tempo_mi,
            "target": _fmt_range_dict(seed.T_min, seed.T_max),
            "intensity": "TEMPO",
        })
        quality_insert = {"type": "tempo", "miles": tempo_mi, "phase": phase}
    
    if easy_mi > 0.5:
        steps.append({
            "name": "Easy",
            "durationType": "DISTANCE",
            "value": easy_mi,
            "target": _fmt_range_dict(seed.E_min, seed.E_max),
            "intensity": "EASY",
        })
    
    steps.append(_cd_step(cd_mi, seed.E_min, seed.E_max))
    
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
        if phase == "Peak":
            cues.append("This is race-specific work. Focus on maintaining consistent effort.")
    
    # Validate and adjust segment totals
    steps = _validate_and_adjust_segments(steps, distance_mi, seed)
    
    cues_str = " ".join(cues)
    return {
        "segments": {
            "units": DEFAULT_UNITS,
            "targetType": "PACE",
            "steps": steps,
            "notes": cues_str,
        },
        "cues": cues_str,
        "pace_labels": {
            "E": pace_range_to_str(seed.E_min, seed.E_max),
            "S": pace_range_to_str(seed.S_min, seed.S_max),
            "M": pace_range_to_str(seed.M, seed.M),
            "T": pace_range_to_str(seed.T_min, seed.T_max),
        },
        "quality_insert": quality_insert,
    }


def _detail_intervals(
    distance_mi: float,
    phase: str,
    seed: PaceSeed,
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
        seed: PaceSeed with pace zones
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
    steps.append(_wu_step(wu_mi, seed.E_min, seed.E_max))
    
    total_interval_mi = 0.0
    for i in range(1, reps + 1):
        # Interval step
        steps.append({
            "name": f"Interval {i}",
            "durationType": "DISTANCE",
            "value": interval_mi,
            "target": _fmt_range_dict(seed.T_min - 15, seed.T_min),  # Slightly faster than T
            "intensity": "INTERVAL",
        })
        total_interval_mi += interval_mi
        
        # Recovery (not after last interval)
        if i < reps:
            steps.append({
                "name": "Recovery",
                "durationType": "DISTANCE",
                "value": recovery_mi,
                "target": _fmt_range_dict(seed.E_min, seed.E_max),
                "intensity": "RECOVERY",
            })
    
    steps.append(_cd_step(cd_mi, seed.E_min, seed.E_max))
    
    quality_insert = {"type": "intervals", "reps": reps, "interval_mi": interval_mi}
    
    cues.append(
        f"Interval workout: {reps} × {interval_mi:.2f} mi at hard effort "
        f"with {recovery_mi:.2f} mi easy jog recovery between."
    )
    cues.append("Run intervals at a controlled hard effort - fast but sustainable.")
    
    if phase == "Peak":
        cues.append("These are race-sharpening intervals. Stay relaxed and powerful.")
    
    # Validate and adjust segment totals
    steps = _validate_and_adjust_segments(steps, distance_mi, seed)
    
    cues_str = " ".join(cues)
    return {
        "segments": {
            "units": DEFAULT_UNITS,
            "targetType": "PACE",
            "steps": steps,
            "notes": cues_str,
        },
        "cues": cues_str,
        "pace_labels": {
            "E": pace_range_to_str(seed.E_min, seed.E_max),
            "S": pace_range_to_str(seed.S_min, seed.S_max),
            "M": pace_range_to_str(seed.M, seed.M),
            "T": pace_range_to_str(seed.T_min, seed.T_max),
        },
        "quality_insert": quality_insert,
    }


def _detail_hills(
    distance_mi: float,
    phase: str,
    seed: PaceSeed,
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
        seed: PaceSeed with pace zones
        allow_quality: Whether quality elements are allowed
        
    Returns:
        Dict with segments, cues, pace_labels, quality_insert
    """
    # =========================================================================
    # PHASE RESTRICTION: No hills in Taper - too much stress
    # =========================================================================
    if phase == "Taper":
        # Downgrade to easy run - hills are unsafe during taper
        return _detail_easy_fallback(distance_mi, seed, 
            "Easy run (hills removed for taper). Keep legs fresh for race day.")
    
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
    elif phase == "Peak":
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
    
    steps.append(_wu_step(wu_mi, seed.E_min, seed.E_max))
    
    for i in range(1, reps + 1):
        steps.append({
            "name": f"Hill {i}",
            "durationType": "DISTANCE",
            "value": hill_mi,
            "target": _fmt_range_dict(seed.T_min - 30, seed.T_min),  # Hard effort
            "intensity": "HARD",
        })
        if i < reps:
            steps.append({
                "name": "Jog Down",
                "durationType": "DISTANCE",
                "value": recovery_mi,
                "target": _fmt_range_dict(seed.E_min + 30, seed.E_max + 30),  # Very easy
                "intensity": "RECOVERY",
            })
    
    steps.append(_cd_step(cd_mi, seed.E_min, seed.E_max))
    
    quality_insert = {"type": "hills", "reps": reps, "phase": phase}
    
    # Phase-specific cues
    if phase == "Base":
        cues.append(
            f"Hill workout: {reps} × ~60-90 second hill repeats. "
            "Focus on building strength - don't go all-out."
        )
    elif phase == "Peak":
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
    steps = _validate_and_adjust_segments(steps, distance_mi, seed)
    
    cues_str = " ".join(cues)
    return {
        "segments": {
            "units": DEFAULT_UNITS,
            "targetType": "PACE",
            "steps": steps,
            "notes": cues_str,
        },
        "cues": cues_str,
        "pace_labels": {
            "E": pace_range_to_str(seed.E_min, seed.E_max),
            "S": pace_range_to_str(seed.S_min, seed.S_max),
            "M": pace_range_to_str(seed.M, seed.M),
            "T": pace_range_to_str(seed.T_min, seed.T_max),
        },
        "quality_insert": quality_insert,
    }


# =============================================================================
# MAIN DETAIL GENERATOR - Archetype-based dispatch
# =============================================================================

def _detail_run(
    run_type: str,
    distance_mi: float,
    phase: str,
    seed: PaceSeed,
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
        seed: PaceSeed with pace zones
        allow_quality: Whether to allow quality elements (T-block, M-finish)
        is_cutback: Whether this is a cutback/recovery week

    Returns:
        Dict with:
            - segments: Spec-compliant segments object with units/targetType/steps/notes
            - cues: String with workout cues/guidance
            - pace_labels: Dict of pace labels (E, S, M, T) for display
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
            distance_mi, seed,
            f"Easy run (workout too short for {run_type}). "
            f"Hard workouts need at least {MIN_HARD_WORKOUT_MILES} miles for safe structure."
        )
    
    # =========================================================================
    # SAFETY CHECK #2: No hard workouts during cutback weeks
    # =========================================================================
    # Cutback weeks are for recovery - Step 6 should have already downgraded,
    # but we enforce it here as a safety net
    if is_cutback and archetype in HARD_ARCHETYPES:
        return _detail_easy_fallback(
            distance_mi, seed,
            "Easy recovery run (cutback week). Focus on rest and recovery."
        )
    
    # =========================================================================
    # ROUTE TO APPROPRIATE GENERATOR
    # =========================================================================
    if archetype == ARCHETYPE_TEMPO:
        return _detail_tempo(distance_mi, phase, seed, allow_quality)
    
    if archetype == ARCHETYPE_INTERVALS:
        return _detail_intervals(distance_mi, phase, seed, allow_quality)
    
    if archetype == ARCHETYPE_HILLS:
        return _detail_hills(distance_mi, phase, seed, allow_quality)
    
    # =========================================================================
    # LEGACY GENERATORS - For EASY, STEADY, ENDURANCE, LONG
    # =========================================================================
    steps = []
    cues = []
    quality_insert = None

    # Get WU/CD distances from config
    wu_cd = WU_CD_MI.get(run_type, {"wu": 1.0, "cd": 1.0})
    wu_mi = wu_cd["wu"]
    cd_mi = wu_cd["cd"]

    # Map archetype back to legacy constants for existing logic
    if archetype == ARCHETYPE_EASY or run_type == EASY:
        main_mi = max(0.0, distance_mi - (wu_mi + cd_mi))
        steps = [
            _wu_step(wu_mi, seed.E_min, seed.E_max),
            {
                "name": "Easy",
                "durationType": "DISTANCE",
                "value": main_mi,
                "target": _fmt_range_dict(seed.E_min, seed.E_max),
                "intensity": "EASY",
            },
            _cd_step(cd_mi, seed.E_min, seed.E_max),
        ]
        cues.append("Conversational effort; keep it relaxed.")

        # Strides if enabled per config
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
            steps = [_wu_step(wu_mi, seed.E_min, seed.E_max)]

            # Add intervals with rest between
            for i in range(1, interval_config["reps"] + 1):
                steps.append(
                    _interval_step(
                        i, interval_config["interval_mi"], seed.T_min, seed.T_max
                    )
                )
                if (
                    i < interval_config["reps"]
                ):  # Rest between intervals (not after last)
                    steps.append(
                        _rest_step(interval_config["rest_mi"], seed.E_min, seed.E_max)
                    )

            # Add any remaining steady distance if needed
            if remaining_mi > 0.1:
                steps.append(
                    {
                        "name": "Steady",
                        "durationType": "DISTANCE",
                        "value": remaining_mi,
                        "target": _fmt_range_dict(seed.S_min, seed.S_max),
                        "intensity": "STEADY",
                    }
                )

            steps.append(_cd_step(cd_mi, seed.E_min, seed.E_max))

            cues.append(
                f"Threshold intervals: {interval_config['reps']}×{interval_config['interval_mi']:.2f}mi "
                f"at threshold pace with {interval_config['rest_mi']:.2f}mi easy recovery."
            )
        else:
            # Continuous steady run (Base phase or when quality not allowed)
            main_mi = max(0.0, distance_mi - (wu_mi + cd_mi))
            steps = [
                _wu_step(wu_mi, seed.E_min, seed.E_max),
                {
                    "name": "Steady",
                    "durationType": "DISTANCE",
                    "value": main_mi,
                    "target": _fmt_range_dict(seed.S_min, seed.S_max),
                    "intensity": "STEADY",
                },
                _cd_step(cd_mi, seed.E_min, seed.E_max),
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
            _wu_step(wu_mi, seed.E_min, seed.E_max),
            {
                "name": "Endurance",
                "durationType": "DISTANCE",
                "value": main_mi,
                "target": _fmt_range_dict(seed.S_min, seed.S_max),
                "intensity": "STEADY",
            },
            _cd_step(cd_mi, seed.E_min, seed.E_max),
        ]
        cues.append("Medium-long run; builds fatigue tolerance.")

        if allow_quality and phase == PHASE["PEAK"] and main_mi >= 6.0:
            cues.append("If feeling good: last 2–3 mi at marathon pace.")

    elif archetype == ARCHETYPE_LONG or run_type == LONG:
        # Check marathon finish conditions from config
        m_finish_enabled = (
            phase in MARATHON_FINISH["enabled_phases"]
            and allow_quality
            and distance_mi >= MARATHON_FINISH["min_lr_mi"]
        )

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
                    "target": _fmt_range_dict(seed.E_min, seed.E_max),
                    "intensity": "EASY",
                },
                {
                    "name": "Marathon finish",
                    "durationType": "DISTANCE",
                    "value": finish_mi,
                    "target": {"low": _sec(seed.M), "high": _sec(seed.M)},
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
                    "name": "Long Easy",
                    "durationType": "DISTANCE",
                    "value": distance_mi,
                    "target": _fmt_range_dict(seed.E_min, seed.E_max),
                    "intensity": "EASY",
                }
            ]
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
                "target": _fmt_range_dict(seed.E_min, seed.E_max),
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
        "pace_labels": {
            "E": pace_range_to_str(seed.E_min, seed.E_max),
            "S": pace_range_to_str(seed.S_min, seed.S_max),
            "M": pace_range_to_str(seed.M, seed.M),
            "T": pace_range_to_str(seed.T_min, seed.T_max),
        },
        "quality_insert": quality_insert,
    }


class Pass4WorkoutDetails:
    """Service for adding detailed segments and pace guidance to workouts."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def add_details_to_plan(
        self,
        plan: Dict[str, Any],
        seed: PaceSeed,
        mode: str = "prefill",
        week_logs: Dict[int, List] = None,
    ) -> Dict[str, Any]:
        """
        Add detailed segments to all workouts in a plan.

        Args:
            plan: Plan dict with 'weeks' array (from Pass 3)
            seed: Initial PaceSeed (adjusted per week in rolling mode)
            mode: "prefill" (all weeks) or "rolling" (week 1 only)
            week_logs: Optional dict mapping week_num -> List[WeekLogRun] for adjustments

        Returns:
            Plan dict with detailed segments added to each workout
        """
        if week_logs is None:
            week_logs = {}

        weeks = plan.get("weeks", [])
        if not weeks:
            self.logger.warning("Plan has no weeks - no details to add")
            return plan

        current_seed = seed
        adjusted_seed = False

        for week in weeks:
            week_num = week.get("week_number", 1)
            phase = week.get("phase", PHASE["BASE"])
            workouts = week.get("workouts", [])

            # In rolling mode, only detail week 1
            if mode == "rolling" and week_num > 1:
                self.logger.debug(f"Rolling mode: skipping details for week {week_num}")
                break

            # Adjust seed based on previous week logs (rolling mode)
            if week_num > 1 and week_logs.get(week_num - 1):
                from .weekly_adjuster import adjust_seed_from_week

                prev_week_log = week_logs[week_num - 1]
                current_seed, disable_quality = adjust_seed_from_week(
                    current_seed, prev_week_log
                )
                adjusted_seed = True
                self.logger.info(
                    f"Week {week_num}: Adjusted pace seed from previous week logs "
                    f"(disable_quality={disable_quality})"
                )
            else:
                # Allow quality for Build/Peak phases
                disable_quality = False

            # Determine if quality elements are allowed (from config)
            allow_quality = (phase in QUALITY_ENABLED_PHASES) and not disable_quality
            
            # Check if this is a cutback week (from Step 6)
            is_cutback = week.get("is_cutback", False)

            # ✅ Store seed in week metadata for storage service
            week["_pace_seed"] = {
                "E_min": current_seed.E_min,
                "E_max": current_seed.E_max,
                "S_min": current_seed.S_min,
                "S_max": current_seed.S_max,
                "M": current_seed.M,
                "T_min": current_seed.T_min,
                "T_max": current_seed.T_max,
                "week1_long_cap": current_seed.week1_long_cap,
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
                    run_type, distance_mi, phase, current_seed, allow_quality,
                    is_cutback=is_cutback
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
            self.logger.info("Pace seed adjusted based on week logs")

        return plan

    def add_details_to_week(
        self,
        week: Dict[str, Any],
        seed: PaceSeed,
        allow_quality: bool = False,
    ) -> Dict[str, Any]:
        """
        Add details to a single week (used for rolling updates).

        Args:
            week: Week dict with workouts
            seed: Current PaceSeed (may be adjusted)
            allow_quality: Whether quality elements are allowed

        Returns:
            Week dict with details added
        """
        phase = week.get("phase", PHASE["BASE"])
        workouts = week.get("workouts", [])
        is_cutback = week.get("is_cutback", False)

        # Store seed in week metadata
        week["_pace_seed"] = {
            "E_min": seed.E_min,
            "E_max": seed.E_max,
            "S_min": seed.S_min,
            "S_max": seed.S_max,
            "M": seed.M,
            "T_min": seed.T_min,
            "T_max": seed.T_max,
            "week1_long_cap": seed.week1_long_cap,
        }

        for workout in workouts:
            run_type = workout.get("type", EASY)
            distance_mi = float(
                workout.get("miles", workout.get("distance_miles", 0)) or 0
            )

            if distance_mi <= 0:
                continue

            details = _detail_run(
                run_type, distance_mi, phase, seed, allow_quality,
                is_cutback=is_cutback
            )
            workout["segments"] = details["segments"]
            workout["cues"] = details["cues"]
            workout["pace_labels"] = details["pace_labels"]
            workout["quality_insert"] = details["quality_insert"]

        return week


if __name__ == "__main__":
    # Quick test
    from .pace_seed_service import get_initial_pace_seed
    from src.db.db_session import get_session

    # Create test seed
    seed = PaceSeed(
        E_min=600.0,
        E_max=690.0,
        S_min=570.0,
        S_max=630.0,
        M=540.0,
        T_min=510.0,
        T_max=520.0,
        week1_long_cap=8.0,
    )

    # Test detail generation
    details = _detail_run(EASY, 4.0, "Base", seed, False)
    print(f"Easy run details: {details}")
