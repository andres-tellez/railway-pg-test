"""Long-run spine generation (build curves + week metadata).

Stage E: single deterministic path — :func:`_build_global_pure_curve_miles` then
:func:`_week_dicts_from_long_run_curve`, with :func:`validate_long_run_curve` at the
executor boundary. Legacy imperative spine generation has been removed.
"""

from __future__ import annotations

from typing import Any, List, Dict, Optional, Union, Tuple
from datetime import datetime, date
import logging
import math

logger = logging.getLogger(__name__)

# Import config type for optional parameter
try:
    from src.services.training_plan.v2.race_configs.base_config import (
        RaceDistanceConfig,
    )
except ImportError:
    RaceDistanceConfig = None  # type: ignore

from src.domain.running.invariants import (
    PEAK_LONG_RUN_FLOOR_DEBUG_ASSERT_ENABLED,
    PEAK_LONG_RUN_MIN_FRACTION_OF_GLOBAL_PRE_TAPER_MAX,
)
from src.services.training_plan.v2.shared_v2.rounding_utils import round_to_half_mile


def compute_long_run_peak_week_metadata(
    weeks: List[Dict[str, Any]],
    *,
    taper_weeks: int,
) -> Dict[str, Optional[int]]:
    """
    Week numbers for diagnostics: global max long run in pre-taper vs max inside Peak block.

    ``global_peak_week_number`` can occur early (e.g. before a deload); ``peak_block_peak_week_number``
    reflects the highest long run inside the assigned Peak phase window.
    """
    out: Dict[str, Optional[int]] = {
        "global_peak_week_number": None,
        "peak_block_peak_week_number": None,
    }
    if not weeks:
        return out
    n = len(weeks)
    tw = max(0, min(n, int(taper_weeks)))
    pre = weeks[: n - tw]
    if not pre:
        return out

    def _lr(w: Dict[str, Any]) -> float:
        return float(w.get("long_run_miles") or 0.0)

    g_max = max(_lr(w) for w in pre)
    g_week: Optional[int] = None
    for w in pre:
        if abs(_lr(w) - g_max) <= 0.05:
            g_week = int(w.get("week_number") or 0) or None
            break
    out["global_peak_week_number"] = g_week

    peak_weeks = [w for w in pre if w.get("phase") == "Peak"]
    if not peak_weeks:
        return out
    pb_max = max(_lr(w) for w in peak_weeks)
    for w in peak_weeks:
        if abs(_lr(w) - pb_max) <= 0.05:
            out["peak_block_peak_week_number"] = int(w.get("week_number") or 0) or None
            break
    return out


def compute_cutback_long_run_miles(
    lr: float,
    cutback_factor: float,
    min_lr: float,
    *,
    max_drop_miles: float = 2.0,
    max_reduction_fraction: float = 0.20,
) -> float:
    """
    Deload long-run target: honor ``cutback_factor`` but cap regression.

    - At most ``max_drop_miles`` below the prior week's long run.
    - At most ``max_reduction_fraction`` reduction (e.g. 0.20 → keep >= 80%).
    Picks the *mildest* of the factor-based target and those floors (highest miles).
    """
    if lr <= 0:
        return round_to_half_mile(max(min_lr, lr))
    soft = lr * cutback_factor
    drop_floor = lr - max_drop_miles
    pct_floor = lr * (1.0 - max_reduction_fraction)
    new_lr = max(min_lr, soft, drop_floor, pct_floor)
    if new_lr >= lr - 0.25:
        new_lr = max(min_lr, lr - 1.0)
    new_lr = min(new_lr, lr - 0.25)
    new_lr = max(min_lr, new_lr)
    return round_to_half_mile(new_lr)


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
        # First cutback, no pre-cutback reference - prefer +1 mi/week stair
        return lr + max(inc_miles, min(base_resume_inc, inc_miles * 2))

    weeks_remaining = max_weeks_to_build - current_week + 1
    miles_to_peak = peak - lr

    if miles_to_peak <= 0:
        return min(peak, lr + max(inc_miles, min(base_resume_inc, inc_miles * 2)))

    if weeks_remaining <= 0:
        return lr + max(inc_miles, min(base_resume_inc, inc_miles * 2))

    # Prefer gradual +1 mi/week after cutback unless time pressure forces larger steps
    gradual_resume = lr + inc_miles
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

    # Option 1: Nudge toward pre-cutback, but never exceed a single-week jump cap
    if pre_cutback_lr + 1.0 <= peak:
        aggressive_resume_1 = min(
            max_resume,
            pre_cutback_lr + 1.0,
            lr + max_resume_increment,
        )
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
        # Do not snap back to full pre-cutback load in one week (avoids 14→10→14 oscillation)
        return min(peak, max_resume)
    # Fallback: ensure we always progress from cutback
    return lr + max(inc_miles, min(base_resume_inc, inc_miles * 2))


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


def _finalize_pre_taper_curve_pure(
    curve: List[float],
    *,
    declared_peak_week_num: Optional[int],
    cap_weeks: int,
    cap_miles: float,
    round_to_half: bool,
) -> List[float]:
    """Pure equivalent of fixed-length post-fill monotonic + pre-taper cap (Stage C).

    Operates on a copy of ``curve`` (pre-taper segment only, before taper weeks).
    """
    out = list(curve)
    n = len(out)
    if n == 0:
        return out

    if declared_peak_week_num and declared_peak_week_num > 0:
        peak_idx_local = min(n - 1, int(declared_peak_week_num) - 1)
    else:
        try:
            peak_idx_local = max(range(n), key=lambda i: out[i])
        except Exception:
            peak_idx_local = 0

    for i in range(peak_idx_local + 1, n):
        prev = out[i - 1]
        if out[i] > prev:
            out[i] = prev

    pre_taper_len = n
    start_cap = max(0, pre_taper_len - int(cap_weeks))

    if declared_peak_week_num and declared_peak_week_num > 0:
        peak_idx_for_cap = min(n - 1, int(declared_peak_week_num) - 1)
    else:
        try:
            peak_idx_for_cap = max(range(n), key=lambda i: out[i])
        except Exception:
            peak_idx_for_cap = -1

    for i in range(start_cap, pre_taper_len):
        is_build_phase = i < peak_idx_for_cap
        at_global_long_run_peak = i == peak_idx_for_cap
        if not is_build_phase and not at_global_long_run_peak and out[i] > cap_miles:
            out[i] = (
                round_to_half_mile(cap_miles) if round_to_half else float(cap_miles)
            )

    return out


def _append_taper_miles_pure(
    pre_taper_curve: List[float],
    *,
    ratios: List[float],
    min_lr: float,
    peak: float,
    round_to_half: bool,
) -> List[float]:
    """Pure taper tail (same anchor rule as legacy spine)."""
    taper_anchor = max(
        min_lr,
        max(pre_taper_curve) if pre_taper_curve else float(peak),
    )
    tail: List[float] = []
    for r in ratios:
        t = max(min_lr, taper_anchor * float(r))
        if round_to_half:
            t = round_to_half_mile(t)
        tail.append(float(t))
    return tail


def _pure_start_long_run_lr(
    starting_long_run_miles: float,
    peak_long_run_target: float,
    *,
    non_regressive_slack: float,
    round_to_half: bool,
) -> Tuple[float, float]:
    """Starting long-run miles and peak (shared fixed/dynamic pure curve header)."""
    peak = float(max(0.0, peak_long_run_target))
    current_longest = float(max(0.0, starting_long_run_miles))
    if round_to_half:
        current_longest = round_to_half_mile(current_longest)
    start_floor = round_to_half_mile(max(0.0, current_longest - non_regressive_slack))
    start_lr = max(start_floor, current_longest)
    if round_to_half:
        start_lr = round_to_half_mile(start_lr)
    return start_lr, peak


def _pure_dynamic_long_run_curve(
    starting_long_run_miles: float,
    peak_long_run_target: float,
    *,
    taper_weeks: int,
    inc_miles: float,
    cutback_every: int,
    cutback_factor: float,
    taper_factor: float,
    round_to_half: bool,
    non_regressive_slack: float,
    config: Optional[RaceDistanceConfig],
    unit_system: str,
) -> List[float]:
    """Full dynamic-length long-run mile curve (pure; Stage C2)."""
    start_lr, peak = _pure_start_long_run_lr(
        starting_long_run_miles,
        peak_long_run_target,
        non_regressive_slack=non_regressive_slack,
        round_to_half=round_to_half,
    )
    curve: List[float] = []
    lr = start_lr
    if round_to_half:
        lr = round_to_half_mile(lr)
    curve.append(float(lr))
    peaked = lr >= peak - 1e-6
    week_num = 2
    pre_cutback_lr: Optional[float] = None
    last_was_cutback = False
    weeks_since_last_cutback = 0
    min_lr_dynamic = config.min_long_run_miles if config else 5.0

    while lr < peak - 1e-6:
        if last_was_cutback:
            dynamic_resume = calculate_dynamic_resume(
                lr=lr,
                pre_cutback_lr=pre_cutback_lr,
                peak=peak,
                current_week=week_num,
                max_weeks_to_build=30,
                cutback_every=cutback_every,
                inc_miles=inc_miles,
                base_resume_inc=inc_miles,
                config=config,
                unit_system=unit_system,
            )
            lr = min(peak, dynamic_resume)
            last_was_cutback = False
            weeks_since_last_cutback = 1
        else:
            weeks_since_last_cutback += 1
            should_cutback = weeks_since_last_cutback >= cutback_every and lr < peak
            if should_cutback:
                pre_cutback_lr = lr
                new_lr = compute_cutback_long_run_miles(
                    lr, cutback_factor, min_lr_dynamic
                )
                if new_lr >= lr:
                    new_lr = round_to_half_mile(max(min_lr_dynamic, lr - 1.0))
                lr = new_lr
                last_was_cutback = True
                weeks_since_last_cutback = 0
            else:
                lr = min(peak, lr + inc_miles)

        if round_to_half:
            lr = round_to_half_mile(lr)
        curve.append(float(lr))
        if not peaked and lr >= peak - 1e-6:
            peaked = True
        week_num += 1
        if week_num > 31:
            break

    min_lr = config.min_long_run_miles if config else 5.0
    final_pre = round_to_half_mile(max(min_lr, peak - 1.0))
    curve.append(float(final_pre))

    taper_weeks_actual = (
        min(taper_weeks, len(config.taper_ratios))
        if config
        else max(2, min(3, taper_weeks))
    )
    if config and len(config.taper_ratios) >= taper_weeks_actual:
        ratios = list(config.taper_ratios[:taper_weeks_actual])
    else:
        if taper_weeks_actual == 3:
            ratios = [0.70, 0.50, 0.25]
        else:
            ratios = [taper_factor, 0.40]
    curve.extend(
        _append_taper_miles_pure(
            curve,
            ratios=ratios,
            min_lr=min_lr,
            peak=peak,
            round_to_half=round_to_half,
        )
    )
    return curve


def _pure_fixed_long_run_curve(
    starting_long_run_miles: float,
    total_weeks_in_plan: int,
    peak_long_run_target: float,
    *,
    taper_weeks: int,
    inc_miles: float,
    cutback_every: int,
    cutback_factor: float,
    taper_factor: float,
    round_to_half: bool,
    non_regressive_slack: float,
    single_peak: bool,
    peak_offset_before_taper: int,
    config: Optional[RaceDistanceConfig],
    unit_system: str,
) -> List[float]:
    """Full fixed-length long-run mile curve including maintenance + taper (pure; Stage C2)."""
    start_lr, peak = _pure_start_long_run_lr(
        starting_long_run_miles,
        peak_long_run_target,
        non_regressive_slack=non_regressive_slack,
        round_to_half=round_to_half,
    )
    curve: List[float] = []
    lr = start_lr
    if round_to_half:
        lr = round_to_half_mile(lr)
    curve.append(float(lr))
    peaked = lr >= peak - 1e-6
    declared_peak_week_num: Optional[int] = None

    weeks_since_last_cutback = 0
    max_weeks_to_build = int(total_weeks_in_plan) - int(taper_weeks)
    min_lr = config.min_long_run_miles if config else 5.0
    resume_inc = config.resume_week_increment if config else 2.0
    pre_cutback_lr: Optional[float] = None
    last_was_cutback = False
    i = 2

    while i <= max_weeks_to_build and not peaked:
        if last_was_cutback:
            cap_val = peak if not (single_peak and peaked) else max(0.0, peak - 1.0)
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
            if dynamic_resume <= lr:
                dynamic_resume = lr + resume_inc
            lr = min(cap_val, dynamic_resume)
            last_was_cutback = False
            weeks_since_last_cutback = 1
        else:
            weeks_since_last_cutback += 1
            should_cutback = weeks_since_last_cutback >= cutback_every and lr < peak
            if should_cutback:
                pre_cutback_lr = lr
                new_lr = compute_cutback_long_run_miles(lr, cutback_factor, min_lr)
                if new_lr >= lr:
                    new_lr = round_to_half_mile(max(min_lr, lr - 1.0))
                lr = new_lr
                last_was_cutback = True
                weeks_since_last_cutback = 0
            else:
                cap = peak if not (single_peak and peaked) else max(0.0, peak - 1.0)
                lr = min(cap, lr + inc_miles)

        if round_to_half:
            lr = round_to_half_mile(lr)
        curve.append(float(lr))
        if not peaked and lr >= peak - 1e-6:
            peaked = True
            declared_peak_week_num = i
        i += 1

    if not curve or curve[-1] < peak:
        prev_lr = curve[-1] if curve else 0.0
        safe_candidate = _cap_forced_peak_jump(prev_lr, peak, unit_system)
        cand = (
            round_to_half_mile(safe_candidate)
            if round_to_half
            else float(safe_candidate)
        )
        curve.append(float(cand))
        peaked = cand >= peak - 1e-6
        declared_peak_week_num = len(curve)

    actual_weeks_so_far = len(curve)
    min_required_weeks = actual_weeks_so_far + taper_weeks
    actual_total_weeks = max(min_required_weeks, int(total_weeks_in_plan))
    rem = actual_total_weeks - len(curve)

    if rem > 0:
        taper_slots = taper_weeks
        maintenance_reduction = config.maintenance_reduction if config else 2.0
        recovery_ratio = config.post_peak_recovery_ratio if config else 0.75
        maintenance_target = round_to_half_mile(max(0.0, peak - maintenance_reduction))

        if rem > 0 and (actual_total_weeks - len(curve)) > taper_slots:
            recovery = round_to_half_mile(max(min_lr, peak * recovery_ratio))
            curve.append(float(recovery))

        if (actual_total_weeks - len(curve)) > taper_slots:
            curve.append(float(maintenance_target))

        while (actual_total_weeks - len(curve)) > taper_slots:
            curve.append(float(maintenance_target))

        rem_after_fill = actual_total_weeks - len(curve)
        cap_weeks = int(config.pre_taper_cap_weeks if config else 5)
        cap_miles = float(config.pre_taper_cap_miles if config else 16.0)
        curve = _finalize_pre_taper_curve_pure(
            curve,
            declared_peak_week_num=declared_peak_week_num,
            cap_weeks=cap_weeks,
            cap_miles=cap_miles,
            round_to_half=round_to_half,
        )

        taper_weeks_to_create = min(rem_after_fill, taper_weeks)
        if rem_after_fill < taper_weeks:
            actual_total_weeks = len(curve) + taper_weeks
            taper_weeks_to_create = taper_weeks

        if taper_weeks_to_create > 0:
            if config and len(config.taper_ratios) >= taper_weeks_to_create:
                ratios = list(config.taper_ratios[:taper_weeks_to_create])
            else:
                if taper_weeks == 3:
                    ratios = [0.70, 0.50, 0.25][:taper_weeks_to_create]
                else:
                    ratios = [taper_factor, 0.40][:taper_weeks_to_create]
            curve.extend(
                _append_taper_miles_pure(
                    curve,
                    ratios=ratios,
                    min_lr=min_lr,
                    peak=peak,
                    round_to_half=round_to_half,
                )
            )

    return curve


def _curve_cutback_week_indices(
    curve: List[float],
    *,
    taper_weeks: int,
    drop_mi: float = 0.5,
) -> List[int]:
    """0-based indices in the pre-taper prefix where long run drops by more than ``drop_mi``."""
    if not curve:
        return []
    pre_n = max(0, len(curve) - int(taper_weeks))
    if pre_n < 2:
        return []
    out: List[int] = []
    for i in range(1, pre_n):
        if float(curve[i - 1]) - float(curve[i]) > drop_mi:
            out.append(i)
    return out


_LR_FLOAT_TOL = 1e-5


def capped_peak_training_weeks(total_weeks: int) -> int:
    """Fixed-length Peak block (pre-taper), not proportional to plan length.

    - ``total_weeks <= 16`` → 3 Peak weeks
    - ``17 <= total_weeks <= 24`` → 3 or 4 (3 for 17–21, 4 for 22–24)
    - ``total_weeks > 24`` → 4 Peak weeks
    """
    tw = max(0, int(total_weeks))
    if tw <= 16:
        return 3
    if tw <= 24:
        return 4 if tw >= 22 else 3
    return 4


def assign_training_intent_phases(
    weeks: List[Dict[str, float]],
    taper_weeks: int,
) -> None:
    """Assign user-facing ``Base`` / ``Build`` / ``Peak`` / ``Taper`` and ``is_peak_week``.

    Mutates week dicts in place (``phase``, ``is_peak_week``) after miles are fixed;
    used by :func:`_week_dicts_from_long_run_curve`.

    **Peak** is the last ``K`` pre-taper weeks, where ``K = capped_peak_training_weeks(len(weeks))``
    (capped so it never exceeds ``pre_count``). This is a fixed physiological window, not a
    fraction of plan length. **Base** / **Build** use the same rule as before: ~35% of weeks
    before Peak are Base, the remainder of that prefix are Build.

    ``is_peak_week`` is True for exactly one week: prefer the first week inside the Peak
    block whose long run equals the overall pre-taper maximum; if the max only occurs
    earlier, fall back to that index; if the Peak block never reaches the global max, use
    the first week inside the Peak block at the block's local maximum.
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

    k_peak = min(capped_peak_training_weeks(n), pre_count)
    peak_start_idx = max(0, pre_count - k_peak)

    # Prefer the first week inside the Peak block that hits the pre-taper max, so
    # ``is_peak_week`` stays meaningful when the curve had an earlier local maximum.
    first_peak_idx = None
    for idx in range(peak_start_idx, len(pre_taper)):
        lr = float(pre_taper[idx].get("long_run_miles") or 0.0)
        if abs(lr - peak_lr) <= _LR_FLOAT_TOL:
            first_peak_idx = idx
            break
    if first_peak_idx is None:
        for idx, w in enumerate(pre_taper):
            lr = float(w.get("long_run_miles") or 0.0)
            if abs(lr - peak_lr) <= _LR_FLOAT_TOL:
                first_peak_idx = idx
                break

    if first_peak_idx is None or first_peak_idx < peak_start_idx:
        window = pre_taper[peak_start_idx:]
        if window:
            local_max = max(float(w.get("long_run_miles") or 0.0) for w in window)
            for j, w in enumerate(window):
                lr_w = float(w.get("long_run_miles") or 0.0)
                if abs(lr_w - local_max) <= _LR_FLOAT_TOL:
                    first_peak_idx = peak_start_idx + j
                    break

    count_pre_peak = peak_start_idx
    if count_pre_peak <= 0:
        base_count = 0
    else:
        base_count = max(1, int(round(count_pre_peak * 0.35)))

    for idx, w in enumerate(weeks):
        if idx >= pre_count:
            w["phase"] = "Taper"
            w["is_peak_week"] = False
            continue
        if idx >= peak_start_idx:
            w["phase"] = "Peak"
            w["is_peak_week"] = bool(
                first_peak_idx is not None and idx == first_peak_idx
            )
            continue
        if base_count > 0 and idx < base_count:
            w["phase"] = "Base"
        else:
            w["phase"] = "Build"
        w["is_peak_week"] = False


def _build_global_pure_curve_miles(
    starting_long_run_miles: float,
    total_weeks_in_plan: Optional[int],
    peak_long_run_target: float,
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
) -> List[float]:
    """Pure global mile curve (Stage C2 / D); shared by curve API and executor."""
    derive_length = total_weeks_in_plan is None or total_weeks_in_plan == 0
    tw: Optional[int] = (
        None if total_weeks_in_plan is None else int(total_weeks_in_plan)
    )
    if not derive_length and tw is None:
        wu = weeks_until(race_date)
        tw = wu if wu is not None else 16
        tw = max(12, min(24, int(tw)))

    if derive_length:
        return _pure_dynamic_long_run_curve(
            starting_long_run_miles,
            peak_long_run_target,
            taper_weeks=taper_weeks,
            inc_miles=inc_miles,
            cutback_every=cutback_every,
            cutback_factor=cutback_factor,
            taper_factor=taper_factor,
            round_to_half=round_to_half,
            non_regressive_slack=non_regressive_slack,
            config=config,
            unit_system=unit_system,
        )
    assert tw is not None and tw > 0
    return _pure_fixed_long_run_curve(
        starting_long_run_miles,
        tw,
        peak_long_run_target,
        taper_weeks=taper_weeks,
        inc_miles=inc_miles,
        cutback_every=cutback_every,
        cutback_factor=cutback_factor,
        taper_factor=taper_factor,
        round_to_half=round_to_half,
        non_regressive_slack=non_regressive_slack,
        single_peak=single_peak,
        peak_offset_before_taper=peak_offset_before_taper,
        config=config,
        unit_system=unit_system,
    )


def _validate_pure_curve_at_boundary(
    curve: List[float],
    *,
    peak_long_run_target: float,
    cutback_every: int,
    taper_weeks: int,
    config: Optional[RaceDistanceConfig],
) -> None:
    """Log structured findings from :func:`validate_long_run_curve` (executor boundary)."""
    try:
        from src.services.training_plan.v2.race_configs.marathon_config import (
            MarathonConfig,
        )
        from src.services.training_plan.v2.shared_v2.long_run_curve_validation import (
            validate_long_run_curve,
        )

        vcfg = config if config is not None else MarathonConfig()
        issues = validate_long_run_curve(
            curve,
            vcfg,
            spine_rows=None,
            expected_start_miles=None,
            peak_target_miles=float(peak_long_run_target),
            taper_ratios_override=list(vcfg.taper_ratios),
            cutback_every_override=int(cutback_every),
            taper_weeks_override=int(taper_weeks),
            include_structure_checks=False,
            include_peak_max_check=True,
            include_pass1_progression=False,
            include_phase_quality=True,
        )
        for issue in issues:
            msg = "Long-run curve validation (%s): %s" % (
                issue["code"],
                issue["message"],
            )
            if issue["severity"] == "error":
                logger.warning(msg)
            else:
                logger.info(msg)
    except Exception as ex:
        logger.warning("Long-run curve validation skipped: %s", ex)


def build_target_long_run_curve(
    starting_long_run_miles: float,
    total_weeks_in_plan: Optional[int],
    peak_long_run_target: float,
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
) -> List[float]:
    """Return only the per-week target long-run distances (Stage E).

    Same sequence as :func:`build_long_run_spine_weeks` (pure global curve plus
    calendar Peak band adjustments), so the mile list matches executor week dicts.
    """
    weeks = build_long_run_spine_weeks(
        starting_long_run_miles,
        total_weeks_in_plan,
        peak_long_run_target,
        race_date=race_date,
        taper_weeks=taper_weeks,
        inc_miles=inc_miles,
        cutback_every=cutback_every,
        cutback_factor=cutback_factor,
        taper_factor=taper_factor,
        round_to_half=round_to_half,
        non_regressive_slack=non_regressive_slack,
        single_peak=single_peak,
        peak_offset_before_taper=peak_offset_before_taper,
        config=config,
        unit_system=unit_system,
    )
    return [float(w["long_run_miles"]) for w in weeks]


def _week_dicts_from_long_run_curve(
    curve: List[float],
    *,
    taper_weeks: int,
) -> List[Dict[str, Any]]:
    """Executor: build spine week dicts from a precomputed mile curve (Stage C)."""
    drop_tol = 0.25
    weeks: List[Dict[str, Any]] = []
    for i, lr in enumerate(curve):
        prev = float(curve[i - 1]) if i > 0 else lr
        is_cb = i > 0 and float(lr) < prev - drop_tol
        weeks.append(
            {
                "week_number": i + 1,
                "long_run_miles": float(lr),
                "phase": "",
                "is_cutback": bool(is_cb),
            }
        )
    assign_training_intent_phases(weeks, taper_weeks)
    _meta = compute_long_run_peak_week_metadata(weeks, taper_weeks=taper_weeks)
    for w in weeks:
        w["global_peak_week_number"] = _meta["global_peak_week_number"]
        w["peak_block_peak_week_number"] = _meta["peak_block_peak_week_number"]
    return weeks


def build_long_run_spine_weeks(
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
    """Return full long-run spine week dicts (public executor for week metadata).

    Stage E: :func:`_build_global_pure_curve_miles` → :func:`validate_long_run_curve`
    → :func:`_week_dicts_from_long_run_curve` (single curve build per call).
    """
    logger.info(
        "Long-run spine: executor=curve+validate_long_run_curve+_week_dicts_from_long_run_curve"
    )

    spine_kw = dict(
        race_date=race_date,
        taper_weeks=taper_weeks,
        inc_miles=inc_miles,
        cutback_every=cutback_every,
        cutback_factor=cutback_factor,
        taper_factor=taper_factor,
        round_to_half=round_to_half,
        non_regressive_slack=non_regressive_slack,
        single_peak=single_peak,
        peak_offset_before_taper=peak_offset_before_taper,
        config=config,
        unit_system=unit_system,
    )

    curve = _build_global_pure_curve_miles(
        starting_long_run_miles,
        total_weeks_in_plan,
        peak_long_run_target,
        **spine_kw,
    )
    _validate_pure_curve_at_boundary(
        curve,
        peak_long_run_target=peak_long_run_target,
        cutback_every=cutback_every,
        taper_weeks=taper_weeks,
        config=config,
    )

    weeks = _week_dicts_from_long_run_curve(curve, taper_weeks=taper_weeks)

    taper_start_idx = next(
        (i for i, w in enumerate(weeks) if w.get("phase") == "Taper"),
        len(weeks),
    )
    peak_indices = [
        i for i in range(taper_start_idx) if weeks[i].get("phase") == "Peak"
    ]
    if peak_indices:
        pre_taper = weeks[:taper_start_idx]
        G = max(float(w.get("long_run_miles") or 0.0) for w in pre_taper)
        if G > 0:
            lo_raw = float(PEAK_LONG_RUN_MIN_FRACTION_OF_GLOBAL_PRE_TAPER_MAX) * G
            lo = (
                round_to_half_mile(lo_raw, unit_system=unit_system)
                if round_to_half
                else float(lo_raw)
            )
            hi = (
                round_to_half_mile(G, unit_system=unit_system)
                if round_to_half
                else float(G)
            )
            if lo > hi:
                lo = float(hi)

            n_peak = len(peak_indices)
            clamped: List[float] = []
            for i in peak_indices:
                v = float(weeks[i].get("long_run_miles") or 0.0)
                v = max(lo, min(hi, v))
                if round_to_half:
                    v = round_to_half_mile(v, unit_system=unit_system)
                v = max(lo, min(hi, float(v)))
                clamped.append(v)

            if n_peak == 1:
                weeks[peak_indices[0]]["long_run_miles"] = clamped[0]
            else:
                adjusted: List[float] = []
                for j in range(n_peak):
                    t = j / (n_peak - 1)
                    span = hi - lo
                    descent = hi - span * (0.3 * t)
                    osc = 0.0
                    if span >= 1.0:
                        osc = 0.5 * math.sin(math.pi * t)
                    elif span >= 0.5:
                        osc = 0.25 * math.sin(math.pi * t)
                    cand = descent + osc
                    cand = max(lo, min(hi, cand))
                    if round_to_half:
                        cand = round_to_half_mile(cand, unit_system=unit_system)
                    cand = max(lo, min(hi, float(cand)))
                    blended = max(lo, min(hi, 0.65 * cand + 0.35 * clamped[j]))
                    if round_to_half:
                        blended = round_to_half_mile(blended, unit_system=unit_system)
                    blended = max(lo, min(hi, float(blended)))
                    adjusted.append(blended)

                if len({round(x, 2) for x in adjusted}) == 1 and (hi - lo) >= 0.5:
                    for j in range(n_peak):
                        bump = (j - (n_peak - 1) / 2.0) * 0.5
                        adjusted[j] = max(lo, min(hi, adjusted[j] + bump))
                        if round_to_half:
                            adjusted[j] = round_to_half_mile(
                                adjusted[j], unit_system=unit_system
                            )
                        adjusted[j] = max(lo, min(hi, float(adjusted[j])))

                for idx, lr in zip(peak_indices, adjusted):
                    weeks[idx]["long_run_miles"] = float(lr)

            if PEAK_LONG_RUN_FLOOR_DEBUG_ASSERT_ENABLED:
                peak_weeks_before_taper = [weeks[i] for i in peak_indices]
                assert all(
                    lo - 1e-6 <= float(w["long_run_miles"]) <= hi + 1e-6
                    for w in peak_weeks_before_taper
                ), (
                    "Peak long-run band (debug): "
                    f"G={G}, lo={lo}, hi={hi}, "
                    f"miles={[float(w['long_run_miles']) for w in peak_weeks_before_taper]}"
                )

    return weeks


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
    """Backward-compatible alias for :func:`build_long_run_spine_weeks`."""
    return build_long_run_spine_weeks(
        starting_long_run_miles,
        total_weeks_in_plan,
        peak_long_run_target,
        race_date=race_date,
        taper_weeks=taper_weeks,
        inc_miles=inc_miles,
        cutback_every=cutback_every,
        cutback_factor=cutback_factor,
        taper_factor=taper_factor,
        round_to_half=round_to_half,
        non_regressive_slack=non_regressive_slack,
        single_peak=single_peak,
        peak_offset_before_taper=peak_offset_before_taper,
        config=config,
        unit_system=unit_system,
    )
