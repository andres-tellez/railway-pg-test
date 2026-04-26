from __future__ import annotations

from typing import List, Dict, Optional, Union, Tuple
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

# Import config type for optional parameter
try:
    from src.services.training_plan.v2.race_configs.base_config import (
        RaceDistanceConfig,
    )
except ImportError:
    RaceDistanceConfig = None  # type: ignore

from src.services.training_plan.v2.shared_v2.rounding_utils import round_to_half_mile


def calculate_dynamic_resume(
    lr: float,
    pre_cutback_lr: Optional[float],
    peak: float,
    current_week: int,
    max_weeks_to_build: int,
    cutback_every: int,
    inc_miles: float,
    base_resume_inc: float,
    config: Optional[RaceDistanceConfig],
    unit_system: str = "imperial",
) -> float:
    """Calculate dynamic resume long run based on time constraints.

    CONTRACT:
        - Input:
            * lr: Current long run after cutback (> 0)
            * pre_cutback_lr: Long run before cutback (None if first cutback)
            * peak: Target peak long run (> lr)
            * current_week: Current week number in build phase
            * max_weeks_to_build: Maximum weeks available to build
            * cutback_every: Cutback frequency (from config)
            * inc_miles: Normal weekly increment (from config)
            * base_resume_inc: Base resume increment (from config)
            * config: RaceDistanceConfig (for cutback_factor)
        - Output: Calculated resume long run distance (lr < result <= peak)
        - Side Effects: NONE (pure function)
        - Dependencies: config for cutback_factor

    GUARDRAILS:
        - All values come from config (no hardcoded values)
        - Never returns value > peak
        - Never returns value <= lr (must progress)
        - Pure function (no side effects)

    Strategy:
    1. Calculate weeks remaining until peak must be reached
    2. Calculate miles remaining to peak
    3. Account for future cutbacks (every 4 weeks)
    4. If time-constrained: resume closer to pre-cutback or use +3 miles
    5. If time-available: use gradual approach (cutback + 2 miles)

    Args:
        lr: Current long run after cutback (e.g., 14 miles)
        pre_cutback_lr: Long run before cutback (e.g., 19 miles), None if first cutback
        peak: Target peak (20 miles)
        current_week: Current week number in build phase
        max_weeks_to_build: Maximum weeks available to build (total_weeks - taper_weeks)
        cutback_every: Cutback frequency (4 weeks)
        inc_miles: Normal weekly increment (1.0 mile/week)
        base_resume_inc: Base resume increment (2.0 miles)
        config: RaceDistanceConfig for cutback_factor
        unit_system: "imperial" or "metric" - determines max resume increment limit
            (2.0 miles for metric, 3.0 miles for imperial)

    Returns:
        Calculated resume long run distance
    """
    if pre_cutback_lr is None:
        # First cutback, no pre-cutback reference - use base increment
        return lr + base_resume_inc

    weeks_remaining = max_weeks_to_build - current_week + 1
    miles_to_peak = peak - lr

    if miles_to_peak <= 0:
        # Already at or past peak
        return min(peak, lr + base_resume_inc)

    if weeks_remaining <= 0:
        # No weeks remaining - use base increment
        return lr + base_resume_inc

    # Calculate if gradual progression works
    gradual_resume = lr + base_resume_inc  # e.g., 14 + 2 = 16
    miles_after_gradual = peak - gradual_resume

    if miles_after_gradual <= 0:
        # Gradual resume would reach or exceed peak
        return min(peak, gradual_resume)

    # Calculate weeks needed with gradual progression (+1 mile/week after resume)
    weeks_needed_gradual = (
        miles_after_gradual / inc_miles
    )  # e.g., (20 - 16) / 1 = 4 weeks

    # Account for future cutbacks if we need 4+ weeks
    # Each cutback cycle (every 4 weeks) loses ~25% of one week's progress
    if weeks_needed_gradual >= cutback_every:
        cutback_factor = config.cutback_factor if config else 0.75
        # Estimate: one more cutback cycle might occur
        # This adds complexity, so we'll add a buffer week
        weeks_needed_gradual += 1

    # If we have enough time: use gradual approach
    if weeks_needed_gradual <= weeks_remaining:
        return gradual_resume

    # Time-constrained: need to accelerate
    # SAFETY: Maximum safe resume increment is 2-3 miles to prevent injury risk
    # Research shows 10-20% weekly increases are safe; 4 miles from 14 = 29% (too aggressive)
    # Recommended: 1-2 miles per week after cutback (14 → 16 → 18 → 20)
    # We allow up to 3 miles for time-constrained scenarios, but prefer gradual
    # CRITICAL: Unit-aware limit to match validation rules
    # Metric: 3.2 km = 1.988 miles, use 2.0 miles to stay within validation limit
    # Imperial: 3.0 miles is acceptable (validation allows cutback rebounds to pass)
    if unit_system == "metric":
        max_resume_increment = (
            2.0  # 2.0 miles = 3.22 km (within 3.2 km validation limit)
        )
    else:
        max_resume_increment = (
            3.0  # Imperial: 3.0 miles (validation allows cutback rebounds)
        )
    max_resume = lr + max_resume_increment

    # Option 1: Resume to pre-cutback + 1 (if close to peak), but cap at max_resume
    if pre_cutback_lr + 1.0 <= peak:
        aggressive_resume_1 = min(
            max_resume, pre_cutback_lr + 1.0
        )  # e.g., min(18, 20) = 18
        miles_after_aggressive_1 = peak - aggressive_resume_1
        weeks_needed_1 = max(0, miles_after_aggressive_1 / inc_miles)

        if weeks_needed_1 <= weeks_remaining:
            return min(peak, aggressive_resume_1)

    # Option 2: Cutback + max_resume_increment (more aggressive than +2), but cap at max_resume
    aggressive_resume_2 = min(
        max_resume, lr + max_resume_increment
    )  # e.g., min(18, 17) = 17
    miles_after_aggressive_2 = peak - aggressive_resume_2

    if miles_after_aggressive_2 > 0:
        weeks_needed_2 = (
            miles_after_aggressive_2 / inc_miles
        )  # e.g., (20 - 17) / 1 = 3 weeks

        # Account for potential cutback if needed
        if weeks_needed_2 >= cutback_every:
            weeks_needed_2 += 1

        if weeks_needed_2 <= weeks_remaining:
            return aggressive_resume_2

    # Very time-constrained: resume to pre-cutback level (safety fallback)
    # GUARDRAIL: Ensure we never return a value <= lr (cutback value) - this would look like another cutback
    # Also cap at max_resume to prevent dangerous jumps
    # Use same unit-aware limit as above
    if unit_system == "metric":
        max_resume_increment = (
            2.0  # 2.0 miles = 3.22 km (within 3.2 km validation limit)
        )
    else:
        max_resume_increment = (
            3.0  # Imperial: 3.0 miles (validation allows cutback rebounds)
        )
    max_resume = lr + max_resume_increment

    if pre_cutback_lr is not None and pre_cutback_lr > lr:
        # Cap at max_resume to prevent dangerous jumps (e.g., 14 → 20 is too aggressive)
        return min(peak, min(max_resume, pre_cutback_lr))
    else:
        # Fallback: ensure we always progress from cutback
        return lr + base_resume_inc


def weeks_until(race: Optional[Union[str, date, datetime]]) -> Optional[int]:
    if race is None:
        return None
    try:
        if isinstance(race, (datetime, date)):
            rd = race.date() if isinstance(race, datetime) else race
        else:
            rd = datetime.fromisoformat(race).date()
        today = datetime.utcnow().date()
        return max(1, (rd - today).days // 7)
    except Exception:
        return None


def _cap_forced_peak_jump(previous: float, target: float, unit_system: str) -> float:
    """
    Smooth only the synthetic end-of-build peak append.

    This avoids abrupt injections like 15→20 while leaving normal build/cutback
    progression untouched.
    """
    if target <= previous:
        return target
    max_jump = 2.0 if unit_system == "metric" else 3.0
    return min(target, previous + max_jump)


def validate_phase_quality(
    weeks: List[Dict[str, float]],
    *,
    peak: float,
    cutback_every: int,
    taper_weeks: int,
    taper_ratios: List[float],
) -> Tuple[bool, List[str]]:
    """Validate the quality of each phase in the generated spine.

    Returns:
        (is_valid, issues) where issues is a list of quality concerns.
    """
    if not weeks:
        return False, ["Empty spine"]

    issues: List[str] = []
    lr_values = [float(w.get("long_run_miles", 0)) for w in weeks]

    # Find phase boundaries
    peak_idx = lr_values.index(max(lr_values))
    build_phase = lr_values[: peak_idx + 1]
    post_peak_phase = (
        lr_values[peak_idx + 1 : -taper_weeks]
        if taper_weeks > 0
        else lr_values[peak_idx + 1 :]
    )
    # FIX: Taper phase should start AFTER peak, not include it
    # Calculate taper from the end, but ensure it doesn't include the peak week
    if taper_weeks > 0:
        # Taper is the last taper_weeks weeks AFTER the peak
        # If peak is in the last taper_weeks, start taper right after peak
        taper_start_idx = max(peak_idx + 1, len(lr_values) - taper_weeks)
        taper_phase = lr_values[taper_start_idx:]
    else:
        taper_phase = []

    # Phase 1: Build to Peak Quality Checks
    if build_phase:
        # Check 1: Cutback spacing - verify cutbacks happen every cutback_every build weeks
        cutback_weeks = []
        build_week_numbers = []  # Track which build week each cutback occurs at

        # Find all cutbacks in build phase
        build_counter = 0  # Count build weeks (excluding start week)
        for i in range(1, len(build_phase)):
            build_counter += 1
            if (
                build_phase[i] < build_phase[i - 1] - 0.5
            ):  # Significant decrease (cutback)
                cutback_weeks.append(i + 1)  # Week number (1-indexed)
                build_week_numbers.append(build_counter)

        # Check for consecutive cutbacks (should never happen)
        for i in range(1, len(build_phase)):
            if build_phase[i] < build_phase[i - 1] - 0.5:  # Cutback
                if (
                    i > 1 and build_phase[i - 1] < build_phase[i - 2] - 0.5
                ):  # Previous was also cutback
                    issues.append(
                        f"Phase 1 (Build): CONSECUTIVE CUTBACKS detected at weeks {i} and {i+1} "
                        f"({build_phase[i-2]:.1f} → {build_phase[i-1]:.1f} → {build_phase[i]:.1f})"
                    )

        # Verify cutback spacing
        if len(build_week_numbers) > 1:
            for j in range(len(build_week_numbers) - 1):
                spacing = build_week_numbers[j + 1] - build_week_numbers[j]
                if spacing != cutback_every:
                    issues.append(
                        f"Phase 1 (Build): Cutback spacing violation - "
                        f"Cutback at build week {build_week_numbers[j]} (Week {cutback_weeks[j]}) "
                        f"followed by cutback at build week {build_week_numbers[j + 1]} (Week {cutback_weeks[j+1]}) "
                        f"(spacing: {spacing} weeks, expected: {cutback_every} weeks)"
                    )

        # Check if first cutback happens at correct interval
        # First cutback should happen at build week 3 (absolute Week 4) for proper spacing
        # Subsequent cutbacks happen every 4th build week (4, 8, 12...)
        if len(build_week_numbers) > 0:
            first_cutback_week = build_week_numbers[0]
            expected_first_cutback = (
                cutback_every - 1
            )  # Build week 3 for cutback_every=4
            if first_cutback_week != expected_first_cutback:
                issues.append(
                    f"Phase 1 (Build): First cutback at build week {first_cutback_week} (Week {cutback_weeks[0]}), "
                    f"expected at build week {expected_first_cutback}"
                )

        # Check 2: Has adequate cutbacks (every cutback_every weeks)
        cutback_count = len(cutback_weeks)
        build_weeks = len(build_phase) - 1
        min_cutbacks = 1 if build_weeks > cutback_every else 0
        expected_cutbacks = max(min_cutbacks, build_weeks // cutback_every)

        if cutback_count < (expected_cutbacks - 1):
            issues.append(
                f"Phase 1 (Build): Only {cutback_count} cutbacks found, expected ~{expected_cutbacks} "
                f"(every {cutback_every} build weeks)"
            )

        # Check 3: Progression is gradual (no jumps >3 miles except after cutback)
        for i in range(1, len(build_phase)):
            if build_phase[i] > build_phase[i - 1]:
                jump = build_phase[i] - build_phase[i - 1]
                # Allow larger jumps after cutbacks (handled separately)
                if i > 1 and build_phase[i - 2] <= build_phase[i - 1]:
                    # Not immediately after cutback
                    if (
                        jump > 3.0
                    ):  # Increased from 2.0 to 3.0 to allow safe resume (14→17)
                        issues.append(
                            f"Phase 1 (Build): Week {i+1} aggressive jump of {jump:.1f} miles (limit: 3.0)"
                        )

        # Check 4: Actually reaches peak
        if build_phase[-1] < peak - 1.0:
            issues.append(
                f"Phase 1 (Build): Never reached peak (max: {build_phase[-1]:.1f}, target: {peak:.1f})"
            )

    # Phase 2: Post-Peak Quality Checks
    if post_peak_phase:
        # Check 1: Non-increasing after peak
        for i in range(1, len(post_peak_phase)):
            if post_peak_phase[i] > post_peak_phase[i - 1]:
                week_num = peak_idx + 1 + i + 1
                issues.append(
                    f"Phase 2 (Post-Peak): Week {week_num} increases after peak ({post_peak_phase[i-1]:.1f} → {post_peak_phase[i]:.1f})"
                )

        # Check 2: Not too high (should be at or below peak-1)
        for i, lr in enumerate(post_peak_phase):
            if lr > peak:
                week_num = peak_idx + 1 + i + 1
                issues.append(
                    f"Phase 2 (Post-Peak): Week {week_num} exceeds peak ({lr:.1f} > {peak:.1f})"
                )

    # Phase 3: Taper Quality Checks
    # NOTE: Taper validation is now handled by PlanValidationServiceV2 with phase-aware
    # and distance-specific rules. The checks here focus only on safety-critical issues.
    if taper_phase:
        # Check 1: Taper length is appropriate (safety-critical)
        if len(taper_phase) < 2:
            issues.append(
                f"Phase 3 (Taper): Too short ({len(taper_phase)} weeks, minimum: 2)"
            )

        # Check 2: Taper is generally decreasing (safety-critical)
        # Allow small fluctuations but flag major increases
        for i in range(1, len(taper_phase)):
            if taper_phase[i] > taper_phase[i - 1] + 1.0:  # Allow 1-mile tolerance
                week_num = len(weeks) - len(taper_phase) + i + 1
                issues.append(
                    f"Phase 3 (Taper): Week {week_num} increases significantly "
                    f"({taper_phase[i-1]:.1f} → {taper_phase[i]:.1f})"
                )

        # REMOVED: Static taper ratio checks (lines 330-338, 348-367)
        # These used peak * taper_ratios which produced unrealistic expectations
        # (e.g., 5 mi final taper for marathon). Now handled by dynamic ratio
        # validation in PlanValidationServiceV2 using final_taper_long_run_range config.

    is_valid = len(issues) == 0
    if not is_valid:
        logger.warning("Spine quality checks failed: %s", "; ".join(issues))

    return is_valid, issues


# Long-run share at/above this fraction of the pre-taper max → Specific phase (plateau / race prep).
SPECIFIC_LR_THRESHOLD_RATIO = 0.9
_LR_FLOAT_TOL = 1e-5


def assign_training_intent_phases(
    weeks: List[Dict[str, float]],
    taper_weeks: int,
    *,
    specific_lr_ratio: float = SPECIFIC_LR_THRESHOLD_RATIO,
) -> None:
    """Assign user-facing ``Base`` / ``Build`` / ``Specific`` / ``Taper`` and ``is_peak_week``.

    Mutates each week dict in place. Once a week qualifies for Specific (long run at or above
    the threshold of the pre-taper maximum), all later pre-taper weeks stay Specific — no
    oscillation back to Build.

    ``is_peak_week`` is True for exactly one week: the first pre-taper week (by list order)
    whose long run equals the pre-taper maximum (ties broken by earliest index).
    """
    if not weeks:
        return
    taper_count = max(0, min(len(weeks), int(taper_weeks)))
    n = len(weeks)
    pre_count = n - taper_count
    if pre_count <= 0:
        for w in weeks:
            w["phase"] = "Taper"
            w["is_peak_week"] = False
        return

    pre_taper = weeks[:pre_count]
    peak_lr = max(float(w.get("long_run_miles") or 0.0) for w in pre_taper)
    thr = peak_lr * float(specific_lr_ratio) - _LR_FLOAT_TOL

    first_specific_idx = None
    for idx, w in enumerate(pre_taper):
        lr = float(w.get("long_run_miles") or 0.0)
        if lr >= thr:
            first_specific_idx = idx
            break
    if first_specific_idx is None:
        first_specific_idx = pre_count - 1

    first_peak_idx = None
    for idx, w in enumerate(pre_taper):
        lr = float(w.get("long_run_miles") or 0.0)
        if abs(lr - peak_lr) <= _LR_FLOAT_TOL:
            first_peak_idx = idx
            break

    count_pre_specific = first_specific_idx  # indices [0, first_specific_idx)
    if count_pre_specific <= 0:
        base_count = 0
    else:
        base_count = max(1, int(round(count_pre_specific * 0.35)))

    for idx, w in enumerate(weeks):
        if idx >= pre_count:
            w["phase"] = "Taper"
            w["is_peak_week"] = False
            continue
        if idx >= first_specific_idx:
            w["phase"] = "Specific"
            w["is_peak_week"] = bool(
                first_peak_idx is not None and idx == first_peak_idx
            )
            continue
        if base_count > 0 and idx < base_count:
            w["phase"] = "Base"
        else:
            w["phase"] = "Build"
        w["is_peak_week"] = False


def generate_long_run_spine(
    starting_long_run_miles: float,
    total_weeks_in_plan: Optional[int],
    peak_long_run_target: float = 20.0,
    *,
    race_date: Optional[Union[str, date, datetime]] = None,
    taper_weeks: int = 2,
    inc_miles: float = 1.0,
    cutback_every: int = 4,
    cutback_factor: float = 0.70,
    taper_factor: float = 0.60,
    round_to_half: bool = True,
    non_regressive_slack: float = 1.0,
    single_peak: bool = True,
    peak_offset_before_taper: int = 1,
    config: Optional[RaceDistanceConfig] = None,
    unit_system: str = "imperial",
) -> List[Dict[str, float]]:
    """Generate a safe long-run progression (spine) for marathon training.

    CONTRACT:
        - Input:
            * starting_long_run_miles > 0
            * peak_long_run_target > starting_long_run_miles
            * total_weeks_in_plan: maximum weeks available (if None, derives organically)
        - Output: List of weeks with long_run_miles that:
            * Starts at starting_long_run_miles (within non_regressive_slack)
            * Reaches peak_long_run_target before taper
            * Has cutbacks every config.cutback_every weeks (or cutback_every param)
            * Respects total_weeks_in_plan as MAXIMUM (not minimum)
            * If extra weeks available, extends build phase with gradual progression
        - Side Effects: NONE (pure function)
        - Dependencies: config (RaceDistanceConfig) for all training parameters

    GUARDRAILS:
        - Never modifies input parameters
        - Never has side effects
        - All values come from config (no hardcoded values)
        - Returns immutable data structure (caller should not modify)
        - If extra weeks available, naturally extends build phase (no post-processing needed)

    ARCHITECTURAL PRINCIPLE:
        This is the SINGLE SOURCE OF TRUTH for long run progression.
        No other component should modify the spine after generation.
        If adjustments are needed, regenerate with different parameters.

    Returns a list of {week_number, long_run_miles, phase}.

    If total_weeks_in_plan is 0 or None, derives length organically:
    builds to peak with +1/week and cutbacks, then adds recovery + taper.
    """
    # Dynamic length mode: derive organically from build to peak + recovery + taper
    derive_length = total_weeks_in_plan is None or total_weeks_in_plan == 0

    if not derive_length and total_weeks_in_plan is None:
        wu = weeks_until(race_date)
        total_weeks_in_plan = wu if wu is not None else 16
        total_weeks_in_plan = max(12, min(24, total_weeks_in_plan))

    peak = float(max(0.0, peak_long_run_target))
    current_longest = float(max(0.0, starting_long_run_miles))
    if round_to_half:
        current_longest = round_to_half_mile(current_longest)

    # Preserve the caller's selected start exactly (no hidden minimum here).
    start_floor = round_to_half_mile(max(0.0, current_longest - non_regressive_slack))
    # Start from user's actual longest recent (no backward step beyond slack)
    start_lr = max(start_floor, current_longest)

    # Start exactly at user's recent ability (within non-regression floor)
    if round_to_half:
        start_lr = round_to_half_mile(start_lr)

    weeks: List[Dict[str, float]] = []
    lr = start_lr
    pre_cutback_lr: Optional[float] = None
    last_was_cutback = False
    peaked = False
    declared_peak_week_num: Optional[int] = None

    # Dynamic length mode: build organically until peak, then add recovery + taper
    if derive_length:
        # Build from start to peak with +1/week and periodic cutbacks
        week_num = 1
        build_counter = 0

        # Append starting week
        if round_to_half:
            lr = round_to_half_mile(lr)
        weeks.append(
            {
                "week_number": week_num,
                "long_run_miles": lr,
                "phase": "Base",
                "is_cutback": False,
            }
        )
        if lr >= peak - 1e-6:
            peaked = True
            declared_peak_week_num = 1
        week_num += 1

        # Build to peak
        min_lr_dynamic = config.min_long_run_miles if config else 5.0
        while lr < peak - 1e-6:
            if last_was_cutback:
                # Resume: use dynamic calculation (same as fixed-length mode)
                # For dynamic mode, we use a large max_weeks_to_build to allow gradual progression
                # This ensures dynamic mode uses gradual approach unless truly constrained
                dynamic_resume = calculate_dynamic_resume(
                    lr=lr,
                    pre_cutback_lr=pre_cutback_lr,
                    peak=peak,
                    current_week=week_num,
                    max_weeks_to_build=30,  # Large number for dynamic mode (no hard constraint)
                    cutback_every=cutback_every,
                    inc_miles=inc_miles,
                    base_resume_inc=inc_miles,  # Use inc_miles as base for dynamic mode
                    config=config,
                    unit_system=unit_system,
                )
                lr = min(peak, dynamic_resume)

                # GUARDRAIL: Log resume for debugging
                logger.debug(
                    f"Week {week_num}: RESUME after cutback (dynamic) - lr {lr:.1f} → {dynamic_resume:.1f} "
                    f"(pre_cutback={pre_cutback_lr}, build_counter reset to 1)"
                )

                last_was_cutback = False
                build_counter = 0
            else:
                # Keep cutback cadence aligned with fixed-length mode:
                # first cutback at build week (cutback_every - 1), then every cutback_every build weeks.
                build_counter += 1
                is_first_cutback = build_counter == cutback_every - 1
                is_subsequent_cutback = (
                    build_counter >= cutback_every
                    and (build_counter % cutback_every) == 0
                )
                if (is_first_cutback or is_subsequent_cutback) and not last_was_cutback:
                    pre_cutback_lr = lr
                    new_lr = round_to_half_mile(
                        max(min_lr_dynamic, lr * cutback_factor)
                    )

                    # GUARDRAIL: Ensure cutback actually reduces long run
                    if new_lr >= lr:
                        logger.warning(
                            f"Week {week_num}: Cutback calculation error (dynamic) - new_lr {new_lr:.1f} >= lr {lr:.1f}, "
                            f"forcing reduction to {lr * 0.7:.1f}"
                        )
                        new_lr = round_to_half_mile(
                            max(min_lr_dynamic, lr * 0.7)
                        )  # Force 30% reduction as fallback

                    # GUARDRAIL: Log cutback for debugging
                    logger.debug(
                        f"Week {week_num}: CUTBACK (dynamic) - lr {lr:.1f} → {new_lr:.1f} "
                        f"(build_counter={build_counter}, factor={cutback_factor:.2f})"
                    )

                    lr = new_lr
                    last_was_cutback = True
                    build_counter = 0
                else:
                    lr = min(peak, lr + inc_miles)

            # Track if this was a cutback week
            week_is_cutback = last_was_cutback  # Set before we clear the flag
            if round_to_half:
                lr = round_to_half_mile(lr)
            weeks.append(
                {
                    "week_number": week_num,
                    "long_run_miles": lr,
                    "phase": "Build",
                    "is_cutback": week_is_cutback,
                }
            )
            if not peaked and lr >= peak - 1e-6:
                peaked = True
                declared_peak_week_num = week_num
            week_num += 1

            # Safety limit
            if week_num > 30:
                break

        # Post-peak: final pre-taper (peak-1), then taper (non-increasing)
        # Skip recovery week to ensure non-increasing post-peak sequence
        min_lr = config.min_long_run_miles if config else 5.0
        final_pre = round_to_half_mile(max(min_lr, peak - 1.0))
        weeks.append(
            {
                "week_number": week_num,
                "long_run_miles": final_pre,
                "phase": "Peak",
                "is_cutback": False,
            }
        )
        week_num += 1

        # Taper: Use config taper_ratios if available, otherwise fallback to defaults
        taper_weeks_actual = (
            min(taper_weeks, len(config.taper_ratios))
            if config
            else max(2, min(3, taper_weeks))
        )
        if config and len(config.taper_ratios) >= taper_weeks_actual:
            ratios = config.taper_ratios[:taper_weeks_actual]
        else:
            # Fallback to hardcoded values for backwards compatibility
            if taper_weeks_actual == 3:
                ratios = [0.70, 0.50, 0.25]
            else:
                ratios = [taper_factor, 0.40]
        taper_anchor = max(
            min_lr,
            max((float(w.get("long_run_miles", 0.0)) for w in weeks), default=peak),
        )
        for r in ratios:
            t = round_to_half_mile(max(min_lr, taper_anchor * r))
            weeks.append(
                {
                    "week_number": week_num,
                    "long_run_miles": t,
                    "phase": "Taper",
                    "is_cutback": False,
                }
            )
            week_num += 1

        assign_training_intent_phases(weeks, taper_weeks_actual)

        # Self-check: Validate phase quality
        # Get taper_ratios from config or use defaults
        if config and hasattr(config, "taper_ratios"):
            validation_taper_ratios = config.taper_ratios
        else:
            # Fallback to defaults for backwards compatibility
            validation_taper_ratios = (
                [0.70, 0.50, 0.25] if taper_weeks_actual >= 3 else [0.70, 0.50]
            )

        is_valid, quality_issues = validate_phase_quality(
            weeks,
            peak=peak,
            cutback_every=cutback_every,
            taper_weeks=taper_weeks_actual,
            taper_ratios=validation_taper_ratios,
        )
        if not is_valid:
            logger.warning(f"Spine quality check failed: {'; '.join(quality_issues)}")

        return weeks

    # Fixed length mode: RESPECT the constraint (treat as MAXIMUM, not minimum)
    # Priority: Reach peak safely, but STAY within total_weeks_in_plan constraint
    # Place peak at total_weeks - taper_weeks - peak_offset_before_taper (initial estimate)
    initial_peak_build_last = max(
        1, total_weeks_in_plan - taper_weeks - max(1, peak_offset_before_taper)
    )

    # Append the starting week as-is (Week 1)
    if round_to_half:
        lr = round_to_half_mile(lr)
    weeks.append(
        {"week_number": 1, "long_run_miles": lr, "phase": "", "is_cutback": False}
    )
    if lr >= peak - 1e-6:
        peaked = True

    # Count build weeks (not absolute week numbers) for proper cutback timing
    # Week 1 is the starting week, so build_counter starts at 0 for Week 2
    # This ensures first cutback happens at Week 4 (build_counter = 3, then increments to 4)
    build_counter = 0

    # Grow from Week 2 onward until we reach peak
    # RESPECT CONSTRAINT: Build until peak is reached, but STAY within total_weeks_in_plan
    # The race date constraint must be respected - don't extend beyond requested weeks
    i = 2
    # FIXED: Use total_weeks_in_plan as maximum (not initial_peak_build_last + 10)
    max_weeks_to_build = (
        total_weeks_in_plan - taper_weeks
    )  # Don't include taper weeks in build limit

    # Build until peak is reached, but respect the maximum weeks constraint
    # Continue until we've reached peak (peaked = True) OR hit the maximum weeks limit
    min_lr = config.min_long_run_miles if config else 5.0
    resume_inc = config.resume_week_increment if config else 2.0

    while i <= max_weeks_to_build and not peaked:
        if last_was_cutback:
            # Resume week: use dynamic calculation based on time constraints
            # This adapts the resume increment (2 vs 3 miles) based on available weeks
            cap_val = peak if not (single_peak and peaked) else max(0.0, peak - 1.0)

            # Calculate dynamic resume based on time pressure
            dynamic_resume = calculate_dynamic_resume(
                lr=lr,
                pre_cutback_lr=pre_cutback_lr,
                peak=peak,
                current_week=i,
                max_weeks_to_build=max_weeks_to_build,
                cutback_every=cutback_every,
                inc_miles=inc_miles,
                base_resume_inc=resume_inc,
                config=config,
                unit_system=unit_system,
            )

            # GUARDRAIL: Resume must ALWAYS increase from cutback value
            # This prevents consecutive cutbacks - resume must be > lr (cutback value)
            if dynamic_resume <= lr:
                logger.warning(
                    f"Week {i}: Dynamic resume returned {dynamic_resume:.1f} <= cutback lr {lr:.1f}, "
                    f"using base increment {resume_inc} as fallback"
                )
                dynamic_resume = lr + resume_inc

            lr = min(cap_val, dynamic_resume)

            # GUARDRAIL: Log resume for debugging
            logger.debug(
                f"Week {i}: RESUME after cutback - lr {lr:.1f} → {dynamic_resume:.1f} "
                f"(pre_cutback={pre_cutback_lr}, build_counter reset to 1)"
            )

            last_was_cutback = False
            current_is_cutback = False
            # GUARDRAIL: Resume week does NOT count toward cutback cycle
            # We need at least cutback_every build weeks AFTER resume before next cutback
            # Start at 0 so we need 4 build weeks (total 4) before next cutback
            build_counter = 0
        else:
            # Increment build counter first, then check for cutback
            # This ensures first cutback happens at Week 4 (after 3 build weeks: Week 2, 3, 4)
            build_counter += 1

            # Check if cutback time: every cutback_every build weeks (not absolute week numbers)
            # First cutback at build week 3 (absolute Week 4), then every 4th build week after that
            # Logic: First cutback when build_counter == 3 (after 3 build weeks)
            #        Subsequent cutbacks when build_counter is a multiple of 4 (4, 8, 12...)
            #        But we need to account for the offset: after first cutback, counter resets to 0
            #        So next cutback should be when counter reaches 4 again (which is 4 build weeks after reset)
            # ADDITIONAL SAFETY: Never allow cutback if we just had a cutback (defensive check)
            is_first_cutback = (
                build_counter == cutback_every - 1
            )  # Week 4: build_counter = 3
            # For subsequent cutbacks: after reset, we need 4 more build weeks (counter = 4, 8, 12...)
            is_subsequent_cutback = (
                build_counter >= cutback_every and (build_counter % cutback_every) == 0
            )

            if (
                (is_first_cutback or is_subsequent_cutback)
                and lr < peak
                and not last_was_cutback
            ):
                pre_cutback_lr = lr
                new_lr = round_to_half_mile(max(min_lr, lr * cutback_factor))

                # GUARDRAIL: Ensure cutback actually reduces long run
                if new_lr >= lr:
                    logger.warning(
                        f"Week {i}: Cutback calculation error - new_lr {new_lr:.1f} >= lr {lr:.1f}, "
                        f"forcing reduction to {lr * 0.7:.1f}"
                    )
                    new_lr = round_to_half_mile(
                        max(min_lr, lr * 0.7)
                    )  # Force 30% reduction as fallback

                # GUARDRAIL: Log cutback for debugging
                logger.debug(
                    f"Week {i}: CUTBACK - lr {lr:.1f} → {new_lr:.1f} "
                    f"(build_counter={build_counter}, factor={cutback_factor:.2f})"
                )

                lr = new_lr
                last_was_cutback = True
                build_counter = 0  # Reset counter after cutback
                # Mark this week as cutback for downstream (Step 6, Step 7)
                current_is_cutback = True
            else:
                cap = peak if not (single_peak and peaked) else max(0.0, peak - 1.0)
                new_lr = min(cap, lr + inc_miles)

                # GUARDRAIL: Log normal build for debugging (only if significant change)
                if abs(new_lr - lr) > 0.1:
                    logger.debug(
                        f"Week {i}: BUILD - lr {lr:.1f} → {new_lr:.1f} "
                        f"(build_counter={build_counter})"
                    )

                lr = new_lr
                current_is_cutback = False

        if round_to_half:
            lr = round_to_half_mile(lr)
        weeks.append(
            {
                "week_number": i,
                "long_run_miles": lr,
                "phase": "",
                "is_cutback": current_is_cutback,
            }
        )
        if not peaked and lr >= peak - 1e-6:
            peaked = True
            declared_peak_week_num = i

        i += 1

    # Ensure final build week keeps progressing, but avoid abrupt forced jumps.
    if not weeks or weeks[-1]["long_run_miles"] < peak:
        prev_lr = weeks[-1]["long_run_miles"] if weeks else 0.0
        safe_candidate = _cap_forced_peak_jump(prev_lr, peak, unit_system)
        peak_week_num = len(weeks) + 1
        weeks.append(
            {
                "week_number": peak_week_num,
                "long_run_miles": round_to_half_mile(safe_candidate),
                "phase": "",
                "is_cutback": False,
            }
        )
        peaked = safe_candidate >= peak - 1e-6
        declared_peak_week_num = peak_week_num

    # Update total_weeks_in_plan to reflect actual plan length
    actual_weeks_so_far = len(weeks)
    # CRITICAL: Ensure we have enough weeks for exactly taper_weeks taper weeks
    # If time-constrained, we may need to extend slightly to accommodate required taper
    # Priority: Ensure taper_weeks are created (safety-critical for race preparation)
    min_required_weeks = actual_weeks_so_far + taper_weeks
    actual_total_weeks = max(
        min_required_weeks,  # At minimum: what we built + required taper weeks
        total_weeks_in_plan,  # But respect the constraint if it's larger
    )
    # If constraint is too tight, log a warning but still ensure taper weeks
    if total_weeks_in_plan > 0 and min_required_weeks > total_weeks_in_plan:
        logger.warning(
            f"Time-constrained plan: Need {min_required_weeks} weeks for proper taper "
            f"but only {total_weeks_in_plan} available. Extending to {min_required_weeks} weeks "
            f"to ensure {taper_weeks} taper weeks are created."
        )

    # Pre-taper fill (maintenance) + Taper weeks
    # Use actual_total_weeks (may be extended for safety) instead of requested total_weeks_in_plan
    wk = len(weeks) + 1
    rem = actual_total_weeks - len(weeks)
    if rem > 0:
        taper_slots = taper_weeks
        min_lr = config.min_long_run_miles if config else 5.0
        maintenance_reduction = config.maintenance_reduction if config else 2.0
        recovery_ratio = config.post_peak_recovery_ratio if config else 0.75

        # Use a safer maintenance target (peak - maintenance_reduction) to avoid sustained 19/20 blocks
        maintenance_target = round_to_half_mile(max(0.0, peak - maintenance_reduction))

        # 1) Immediate recovery week after peak (using config ratio)
        if rem > 0 and (actual_total_weeks - len(weeks)) > taper_slots:
            recovery = round_to_half_mile(max(min_lr, peak * recovery_ratio))
            weeks.append(
                {
                    "week_number": wk,
                    "long_run_miles": recovery,
                    "phase": "",
                    "is_cutback": False,
                }
            )
            wk += 1

        # 2) One sub-peak cap week (peak - maintenance_reduction) if time remains before taper
        if (actual_total_weeks - len(weeks)) > taper_slots:
            weeks.append(
                {
                    "week_number": wk,
                    "long_run_miles": maintenance_target,
                    "phase": "",
                    "is_cutback": False,
                }
            )
            wk += 1

        # 3) Fill any remaining pre-taper weeks with maintenance_target
        while (actual_total_weeks - len(weeks)) > taper_slots:
            weeks.append(
                {
                    "week_number": wk,
                    "long_run_miles": maintenance_target,
                    "phase": "",
                    "is_cutback": False,
                }
            )
            wk += 1

        rem_after_fill = actual_total_weeks - len(weeks)

        # Enforce post-peak monotonic decrease through pre-taper segment
        # Find peak index in current weeks (should exist by construction)
        if declared_peak_week_num and declared_peak_week_num > 0:
            peak_idx_local = min(len(weeks) - 1, declared_peak_week_num - 1)
        else:
            try:
                peak_idx_local = max(
                    range(len(weeks)), key=lambda i: weeks[i]["long_run_miles"]
                )  # noqa: E731
            except Exception:
                peak_idx_local = 0
        for i in range(peak_idx_local + 1, len(weeks)):
            prev = weeks[i - 1]["long_run_miles"]
            if weeks[i]["long_run_miles"] > prev:
                weeks[i]["long_run_miles"] = prev

        # CRITICAL FIX: Cap any long runs within pre-taper cap weeks to config value
        # BUT: Never cap the actual peak week OR any weeks during the build phase
        # The cap should ONLY apply to maintenance weeks AFTER the peak, not during build
        pre_taper_len = max(0, len(weeks))
        cap_weeks = config.pre_taper_cap_weeks if config else 5
        cap_miles = config.pre_taper_cap_miles if config else 16.0
        start_cap = max(0, pre_taper_len - cap_weeks)

        # Find peak index to exclude it and all build weeks from capping
        if declared_peak_week_num and declared_peak_week_num > 0:
            peak_idx_for_cap = min(len(weeks) - 1, declared_peak_week_num - 1)
        else:
            try:
                peak_idx_for_cap = max(
                    range(len(weeks)), key=lambda i: weeks[i]["long_run_miles"]
                )
            except Exception:
                peak_idx_for_cap = -1  # No peak found, safe to cap all

        for i in range(start_cap, pre_taper_len):
            # Don't cap:
            # 1. The peak week itself (preserve 20-mile peak)
            # 2. Any weeks during the build phase (before peak) - this prevents false cutbacks
            # Only cap maintenance weeks AFTER the peak
            is_build_phase = i < peak_idx_for_cap
            at_global_long_run_peak = i == peak_idx_for_cap

            if (
                not is_build_phase
                and not at_global_long_run_peak
                and weeks[i]["long_run_miles"] > cap_miles
            ):
                weeks[i]["long_run_miles"] = round_to_half_mile(cap_miles)

        # CRITICAL FIX: Ensure exactly taper_weeks are created, not just rem_after_fill
        # If rem_after_fill < taper_weeks, we need to extend the plan or reduce pre-taper weeks
        # Priority: Always create exactly taper_weeks for proper race preparation
        taper_weeks_to_create = min(rem_after_fill, taper_weeks)

        # If we don't have enough weeks for full taper, extend the plan
        if rem_after_fill < taper_weeks:
            logger.warning(
                f"Time constraint: Only {rem_after_fill} weeks available for taper, "
                f"but {taper_weeks} required. Extending plan to accommodate full taper."
            )
            # Extend actual_total_weeks to ensure we can create all taper weeks
            actual_total_weeks = len(weeks) + taper_weeks
            taper_weeks_to_create = taper_weeks

        if taper_weeks_to_create > 0:
            # Use config taper ratios if available
            if config and len(config.taper_ratios) >= taper_weeks_to_create:
                ratios = config.taper_ratios[:taper_weeks_to_create]
            else:
                # Fallback to hardcoded values for backwards compatibility
                if taper_weeks == 3:
                    ratios = [0.70, 0.50, 0.25][:taper_weeks_to_create]
                else:
                    ratios = [taper_factor, 0.40][:taper_weeks_to_create]
            taper_anchor = max(
                min_lr,
                max((float(w.get("long_run_miles", 0.0)) for w in weeks), default=peak),
            )
            for r in ratios:
                t = round_to_half_mile(max(min_lr, taper_anchor * r))
                weeks.append(
                    {
                        "week_number": wk,
                        "long_run_miles": t,
                        "phase": "",
                        "is_cutback": False,
                    }
                )
                wk += 1

    assign_training_intent_phases(weeks, taper_weeks)

    return weeks
