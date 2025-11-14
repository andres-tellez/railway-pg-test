from __future__ import annotations

from typing import List, Dict, Optional, Union, Tuple
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


def round_half(x: float) -> float:
    return round(x * 2) / 2.0


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


def validate_phase_quality(
    weeks: List[Dict[str, float]], *, peak: float, cutback_every: int, taper_weeks: int
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
    taper_phase = lr_values[-taper_weeks:] if taper_weeks > 0 else []

    # Phase 1: Build to Peak Quality Checks
    if build_phase:
        # Check 1: Has adequate cutbacks (every 3-4 weeks)
        cutback_count = 0
        for i in range(1, len(build_phase)):
            if build_phase[i] < build_phase[i - 1]:
                cutback_count += 1

        # Build weeks = total weeks - 1 (excluding start week)
        build_weeks = len(build_phase) - 1
        # Minimum cutbacks needed: at least 1 for plans > cutback_every weeks
        # Expected: one cutback per cutback_every build weeks
        min_cutbacks = 1 if build_weeks > cutback_every else 0
        expected_cutbacks = max(min_cutbacks, build_weeks // cutback_every)

        # Only flag if significantly fewer cutbacks than expected (allow 1 less for rounding)
        if cutback_count < (expected_cutbacks - 1):
            issues.append(
                f"Phase 1 (Build): Only {cutback_count} cutbacks found, expected ~{expected_cutbacks} (every {cutback_every} build weeks)"
            )

        # Check 2: Progression is gradual (no jumps >2 miles except after cutback)
        for i in range(1, len(build_phase)):
            if build_phase[i] > build_phase[i - 1]:
                jump = build_phase[i] - build_phase[i - 1]
                # Allow larger jumps after cutbacks (handled separately)
                if i > 1 and build_phase[i - 2] <= build_phase[i - 1]:
                    # Not immediately after cutback
                    if jump > 2.0:
                        issues.append(
                            f"Phase 1 (Build): Week {i+1} aggressive jump of {jump:.1f} miles (limit: 2.0)"
                        )

        # Check 3: Actually reaches peak
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
    if taper_phase:
        # Check 1: Taper length is appropriate
        if len(taper_phase) < 2:
            issues.append(
                f"Phase 3 (Taper): Too short ({len(taper_phase)} weeks, minimum: 2)"
            )

        # Check 2: Taper ratios are correct (should be decreasing: 70%, 50%, 25% for 3-week taper)
        if len(taper_phase) == 3:
            expected = [peak * 0.70, peak * 0.50, peak * 0.25]
            for i, (actual, exp) in enumerate(zip(taper_phase, expected)):
                week_num = len(weeks) - len(taper_phase) + i + 1
                if abs(actual - exp) > 2.0:  # Allow 2-mile tolerance
                    issues.append(
                        f"Phase 3 (Taper): Week {week_num} ratio off (got {actual:.1f}, expected ~{exp:.1f})"
                    )

        # Check 3: Taper is strictly decreasing
        for i in range(1, len(taper_phase)):
            if taper_phase[i] >= taper_phase[i - 1]:
                week_num = len(weeks) - len(taper_phase) + i + 1
                issues.append(
                    f"Phase 3 (Taper): Week {week_num} not decreasing ({taper_phase[i-1]:.1f} → {taper_phase[i]:.1f})"
                )

        # Check 4: Final week should be low (≤6 miles for race week)
        if taper_phase[-1] > 6.0:
            issues.append(
                f"Phase 3 (Taper): Final week too high ({taper_phase[-1]:.1f} miles, should be ≤6 for race week)"
            )

    is_valid = len(issues) == 0
    if not is_valid:
        logger.warning("Spine quality checks failed: %s", "; ".join(issues))

    return is_valid, issues


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
) -> List[Dict[str, float]]:
    """Generate a safe long-run progression (spine) for marathon training.

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

    peak = float(min(20.0, peak_long_run_target))
    current_longest = float(max(0.0, starting_long_run_miles))
    if round_to_half:
        current_longest = round_half(current_longest)

    # Preserve the caller's selected start exactly (no hidden minimum here).
    start_floor = round_half(max(0.0, current_longest - non_regressive_slack))
    # Start from user's actual longest recent (no backward step beyond slack)
    start_lr = max(start_floor, current_longest)

    # Start exactly at user's recent ability (within non-regression floor)
    if round_to_half:
        start_lr = round_half(start_lr)

    weeks: List[Dict[str, float]] = []
    lr = start_lr
    pre_cutback_lr: Optional[float] = None
    last_was_cutback = False
    peaked = False

    # Dynamic length mode: build organically until peak, then add recovery + taper
    if derive_length:
        # Build from start to peak with +1/week and periodic cutbacks
        week_num = 1
        build_counter = 0

        # Append starting week
        if round_to_half:
            lr = round_half(lr)
        weeks.append({"week_number": week_num, "long_run_miles": lr, "phase": "Base"})
        if lr >= peak - 1e-6:
            peaked = True
        week_num += 1
        build_counter += 1

        # Build to peak
        while lr < peak - 1e-6:
            if last_was_cutback:
                # Resume: pre-cutback + 1.0 (e.g., 17 → 12 cutback, then 18 resume)
                if pre_cutback_lr is not None:
                    resume_target = pre_cutback_lr + inc_miles
                else:
                    resume_target = lr + inc_miles
                lr = min(peak, resume_target)
                last_was_cutback = False
                build_counter = 1
            else:
                # Check if cutback time: every cutback_every build weeks
                if build_counter > 0 and (build_counter % cutback_every) == 0:
                    pre_cutback_lr = lr
                    lr = round_half(max(5.0, lr * cutback_factor))
                    last_was_cutback = True
                    build_counter = 0
                else:
                    lr = min(peak, lr + inc_miles)
                    build_counter += 1

            if round_to_half:
                lr = round_half(lr)
            weeks.append(
                {"week_number": week_num, "long_run_miles": lr, "phase": "Build"}
            )
            if not peaked and lr >= peak - 1e-6:
                peaked = True
            week_num += 1

            # Safety limit
            if week_num > 30:
                break

        # Post-peak: final pre-taper (peak-1), then taper (non-increasing)
        # Skip recovery week to ensure non-increasing post-peak sequence
        final_pre = round_half(max(5.0, peak - 1.0))
        weeks.append(
            {"week_number": week_num, "long_run_miles": final_pre, "phase": "Peak"}
        )
        week_num += 1

        # Taper: 3 weeks at 70%, 50%, 25% of peak
        taper_weeks_actual = max(2, min(3, taper_weeks))
        if taper_weeks_actual == 3:
            ratios = [0.70, 0.50, 0.25]
        else:
            ratios = [taper_factor, 0.40]
        for r in ratios[:taper_weeks_actual]:
            t = round_half(max(5.0, peak * r))
            weeks.append(
                {"week_number": week_num, "long_run_miles": t, "phase": "Taper"}
            )
            week_num += 1

        # Re-label phases more accurately
        total = len(weeks)
        for i, w in enumerate(weeks):
            wn = int(w["week_number"])
            if i < total // 4:
                w["phase"] = "Base"
            elif i < total // 2:
                w["phase"] = "Build"
            elif i < total - taper_weeks_actual:
                w["phase"] = "Peak"
            else:
                w["phase"] = "Taper"

        # Self-check: Validate phase quality
        is_valid, quality_issues = validate_phase_quality(
            weeks,
            peak=peak,
            cutback_every=cutback_every,
            taper_weeks=taper_weeks_actual,
        )
        if not is_valid:
            logger.warning(f"Spine quality check failed: {'; '.join(quality_issues)}")

        return weeks

    # Fixed length mode (legacy): use provided total_weeks_in_plan
    # Place peak at total_weeks - taper_weeks - peak_offset_before_taper
    peak_build_last = max(
        1, total_weeks_in_plan - taper_weeks - max(1, peak_offset_before_taper)
    )

    # Append the starting week as-is (Week 1)
    if round_to_half:
        lr = round_half(lr)
    weeks.append({"week_number": 1, "long_run_miles": lr, "phase": ""})
    if lr >= peak - 1e-6:
        peaked = True

    # Grow from Week 2 onward
    for i in range(2, peak_build_last + 1):
        if last_was_cutback:
            # Resume week: increase from the cutback week more gently (+2.0),
            # and also cap against pre-cutback + 2 to avoid aggressive jumps.
            cap_val = peak if not (single_peak and peaked) else max(0.0, peak - 1.0)
            gentle_step = lr + 2.0  # e.g., 12 -> 14
            upper_bound = (pre_cutback_lr or lr) + 2.0
            target = min(gentle_step, upper_bound)
            lr = min(cap_val, target)
            last_was_cutback = False
        else:
            if (i % cutback_every) == 0 and lr < peak:
                pre_cutback_lr = lr
                lr = lr * cutback_factor
                last_was_cutback = True
            else:
                cap = peak if not (single_peak and peaked) else max(0.0, peak - 1.0)
                lr = min(cap, lr + inc_miles)

        if round_to_half:
            lr = round_half(lr)
        weeks.append({"week_number": i, "long_run_miles": lr, "phase": ""})
        if not peaked and lr >= peak - 1e-6:
            peaked = True

    # Ensure peak present at end of build
    if not weeks or weeks[-1]["long_run_miles"] < peak:
        weeks.append(
            {
                "week_number": len(weeks) + 1,
                "long_run_miles": round_half(peak),
                "phase": "",
            }
        )

    # Pre-taper fill (maintenance) + Taper weeks to exactly hit total_weeks_in_plan
    wk = len(weeks) + 1
    rem = total_weeks_in_plan - len(weeks)
    if rem > 0:
        taper_slots = taper_weeks
        # Use a safer maintenance target (peak - 2) to avoid sustained 19/20 blocks
        maintenance_target = round_half(max(0.0, peak - 2.0))

        # 1) Immediate recovery week after peak (~25% reduction)
        if rem > 0 and (total_weeks_in_plan - len(weeks)) > taper_slots:
            recovery = round_half(max(5.0, peak * 0.75))
            weeks.append({"week_number": wk, "long_run_miles": recovery, "phase": ""})
            wk += 1

        # 2) One sub-peak cap week (peak - 2) if time remains before taper
        if (total_weeks_in_plan - len(weeks)) > taper_slots:
            weeks.append(
                {"week_number": wk, "long_run_miles": maintenance_target, "phase": ""}
            )
            wk += 1

        # 3) Fill any remaining pre-taper weeks with maintenance_target
        while (total_weeks_in_plan - len(weeks)) > taper_slots:
            weeks.append(
                {"week_number": wk, "long_run_miles": maintenance_target, "phase": ""}
            )
            wk += 1

        rem_after_fill = total_weeks_in_plan - len(weeks)

        # Enforce post-peak monotonic decrease through pre-taper segment
        # Find peak index in current weeks (should exist by construction)
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

        # Cap any long runs within the last 5 weeks before taper (outside taper) to ≤16
        pre_taper_len = max(0, len(weeks))
        start_cap = max(0, pre_taper_len - 5)
        for i in range(start_cap, pre_taper_len):
            if weeks[i]["long_run_miles"] > 16.0:
                weeks[i]["long_run_miles"] = 16.0
        if rem_after_fill > 0:
            if taper_weeks == 3:
                ratios = [0.70, 0.50, 0.25][:rem_after_fill]
            else:
                ratios = [taper_factor, 0.40][:rem_after_fill]
            for r in ratios:
                t = round_half(max(5.0, peak * r))
                weeks.append({"week_number": wk, "long_run_miles": t, "phase": ""})
                wk += 1

    # Label phases
    for w in weeks:
        i = int(w["week_number"])
        if i <= max(1, total_weeks_in_plan // 4):
            w["phase"] = "Base"
        elif i <= max(2, total_weeks_in_plan // 2):
            w["phase"] = "Build"
        elif i <= total_weeks_in_plan - taper_weeks - 1:
            w["phase"] = "Peak"
        else:
            w["phase"] = "Taper"

    return weeks
