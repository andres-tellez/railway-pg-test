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

from .workout_types import EASY, STEADY, ENDURANCE, LONG, TYPE_DISPLAY
from .pace_seed_service import PaceSeed
from .workout_detail_rules import (
    PHASE,
    WU_CD_MI,
    STRIDES,
    MARATHON_FINISH,
    QUALITY_ENABLED_PHASES,
    DEFAULT_UNITS,
)

logger = logging.getLogger(__name__)


# ---------- Helper Functions ----------


def _sec(s: float) -> int:
    """Convert seconds (float) to integer seconds."""
    return int(round(s))


def _fmt_range_dict(min_sec: float, max_sec: float) -> dict:
    """Format pace range as dict with low/high in seconds."""
    return {"low": _sec(min_sec), "high": _sec(max_sec)}


def _fmt_range_str(min_sec: float, max_sec: float) -> str:
    """Format pace range as string (for pace_labels display)."""

    def mmss(sec: float) -> str:
        m = int(sec // 60)
        s = int(round(sec - 60 * m))
        return f"{m}:{s:02d}"

    if abs(min_sec - max_sec) < 1.0:
        return f"{mmss(min_sec)}/mi"
    return f"{mmss(min_sec)}–{mmss(max_sec)}/mi"


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


def _detail_run(
    run_type: str,
    distance_mi: float,
    phase: str,
    seed: PaceSeed,
    allow_quality: bool,
) -> Dict[str, Any]:
    """
    Generate detailed segments and cues (spec-compliant).

    Now uses config module and filters zero/negative steps.

    Args:
        run_type: Workout type (EASY, STEADY, ENDURANCE, LONG)
        distance_mi: Total distance in miles
        phase: Training phase (Base, Build, Peak, Taper)
        seed: PaceSeed with pace zones
        allow_quality: Whether to allow quality elements (T-block, M-finish)

    Returns:
        Dict with:
            - segments: Spec-compliant segments object with units/targetType/steps/notes
            - cues: String with workout cues/guidance
            - pace_labels: Dict of pace labels (E, S, M, T) for display
            - quality_insert: Optional quality insert metadata
    """
    steps = []
    cues = []
    quality_insert = None

    # Get WU/CD distances from config
    wu_cd = WU_CD_MI.get(run_type, {"wu": 1.0, "cd": 1.0})
    wu_mi = wu_cd["wu"]
    cd_mi = wu_cd["cd"]

    if run_type == EASY:
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

    elif run_type == STEADY:
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

    elif run_type == ENDURANCE:
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

    elif run_type == LONG:
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
            "E": _fmt_range_str(seed.E_min, seed.E_max),
            "S": _fmt_range_str(seed.S_min, seed.S_max),
            "M": _fmt_range_str(seed.M, seed.M),
            "T": _fmt_range_str(seed.T_min, seed.T_max),
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

                # Generate detailed segments
                details = _detail_run(
                    run_type, distance_mi, phase, current_seed, allow_quality
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

            details = _detail_run(run_type, distance_mi, phase, seed, allow_quality)
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
