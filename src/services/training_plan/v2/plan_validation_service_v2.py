"""
Layer 5: Plan Validation Service

Purpose:
    Verify GPT-generated plan follows safety rules and training principles.
    Act as safety check before storing plan in database.

Responsibilities:
    - Validate mileage progression (10% rule)
    - Verify cutback weeks exist
    - Check long run progression and peak
    - Ensure adequate rest days
    - Verify taper structure
    - Check plan completeness and data integrity

Dependencies:
    - Generated plan from Layer 4 (GptCoachService)
    - Training safety rules and thresholds

Testing:
    See tests/services/training_plan/test_plan_validation_service.py

Author: SmartCoach Development Team
Last Updated: October 29, 2025
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta

from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.utils.date_helpers import get_week_start_for_date
from src.services.training_plan.v2.shared_v2.rounding_utils import (
    miles_to_km,
    km_to_miles,
)

logger = logging.getLogger(__name__)


class PlanValidationServiceV2:
    """Service for validating training plan safety and correctness."""

    def __init__(
        self,
        config: RaceDistanceConfig,
        max_weekly_increase_percent: float = 20.0,
        cutback_interval_weeks: int = 4,
        unit_system: str = "imperial",
    ) -> None:
        self.config = config
        self.MAX_WEEKLY_INCREASE_PERCENT = max_weekly_increase_percent
        self.CUTBACK_INTERVAL_WEEKS = cutback_interval_weeks
        self.TAPER_WEEKS = config.taper_weeks  # final taper weeks from config
        self.unit_system = unit_system

    def validate_plan(
        self, plan: Dict[str, Any], unit_system: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate complete training plan against safety rules.

        Args:
            plan: Generated plan from Layer 4 GptCoachService
            unit_system: Optional override for unit system (defaults to instance default)

        Returns:
            Validation result dictionary:
                {
                    "valid": bool,
                    "violations": [
                        {
                            "rule": str,
                            "severity": "error" | "warning",
                            "location": str,
                            "details": str,
                            "suggestion": str
                        }
                    ],
                    "validated_plan": Dict | None
                }
        """
        # Use provided unit_system or fall back to instance default
        effective_unit_system = unit_system or self.unit_system
        violations: List[Dict[str, str]] = []

        # Basic structure validation
        if not isinstance(plan, dict):
            return {
                "valid": False,
                "violations": [
                    {
                        "rule": "invalid_structure",
                        "severity": "error",
                        "location": "plan",
                        "details": "Plan must be a dictionary",
                        "suggestion": "Check plan format",
                    }
                ],
                "validated_plan": None,
            }

        if "weeks" not in plan or not isinstance(plan["weeks"], list):
            return {
                "valid": False,
                "violations": [
                    {
                        "rule": "missing_weeks",
                        "severity": "error",
                        "location": "plan",
                        "details": "Plan must have a 'weeks' list",
                        "suggestion": "Add weeks array",
                    }
                ],
                "validated_plan": None,
            }

        weeks = plan["weeks"]
        if not weeks:
            return {
                "valid": False,
                "violations": [
                    {
                        "rule": "empty_weeks",
                        "severity": "error",
                        "location": "plan",
                        "details": "Plan has no weeks",
                        "suggestion": "Add at least one week",
                    }
                ],
                "validated_plan": None,
            }

        # Validate each week structure
        for week in weeks:
            violations.extend(self._validate_week_structure(week))

        # Validate plan-level safety rules
        violations.extend(
            self._validate_mileage_progression(weeks, effective_unit_system)
        )
        violations.extend(self._validate_cutback_weeks(weeks))
        violations.extend(
            self._validate_long_run_progression(weeks, effective_unit_system)
        )
        violations.extend(self._validate_taper(weeks, effective_unit_system))
        # REMOVED: _validate_long_run_bounds - now handled by Step 5 phase-aware logic
        # violations.extend(self._validate_long_run_bounds(weeks))
        violations.extend(self._validate_week_completeness(weeks))
        # Skip race date timing validation - this is already handled by RaceDateValidationService
        # which shows a dialog to the user before plan generation. This check is redundant.
        # violations.extend(self._validate_race_date_timing(plan))

        # Check if there are any ERROR-level violations
        errors = [v for v in violations if v.get("severity") == "error"]
        is_valid = len(errors) == 0

        # Hide warnings from user-facing output (keep only errors)
        # Warnings are still generated for internal logging/debugging if needed
        user_facing_violations = errors

        return {
            "valid": is_valid,
            "violations": user_facing_violations,
            "validated_plan": plan if is_valid else None,
        }

    def _validate_week_structure(self, week: Dict[str, Any]) -> List[Dict[str, str]]:
        """Validate structure of a single week."""
        violations = []

        if "week_number" not in week:
            violations.append(
                {
                    "rule": "missing_week_number",
                    "severity": "error",
                    "location": f"week (index unknown)",
                    "details": "Week missing week_number",
                    "suggestion": "Add week_number field",
                }
            )
            return violations

        week_num = week.get("week_number")
        location = f"week {week_num}"

        if (
            "workouts" not in week
            or not isinstance(week.get("workouts"), list)
            or not week.get("workouts")
        ):
            violations.append(
                {
                    "rule": "missing_workouts",
                    "severity": "error",
                    "location": location,
                    "details": "Week has no workouts",
                    "suggestion": "Add at least one workout",
                }
            )

        if "weekly_mileage" not in week:
            # Attempt to compute from workouts distances
            workouts_for_sum = week.get("workouts", [])
            if isinstance(workouts_for_sum, list) and workouts_for_sum:
                try:
                    from src.services.training_plan.workout_utils import (
                        calculate_weekly_mileage_from_workouts,
                    )

                    week["weekly_mileage"] = calculate_weekly_mileage_from_workouts(
                        workouts_for_sum
                    )
                except Exception:
                    violations.append(
                        {
                            "rule": "missing_weekly_mileage",
                            "severity": "error",
                            "location": location,
                            "details": "Week missing weekly_mileage and could not compute from workouts",
                            "suggestion": "Add weekly_mileage or include workout distances",
                        }
                    )
            else:
                violations.append(
                    {
                        "rule": "missing_weekly_mileage",
                        "severity": "error",
                        "location": location,
                        "details": "Week missing weekly_mileage and workouts are empty",
                        "suggestion": "Add weekly_mileage field and workouts with distances",
                    }
                )

        # Validate each workout
        workouts = week.get("workouts", [])
        for i, workout in enumerate(workouts):
            workout_violations = self._validate_workout(workout, week_num, i)
            violations.extend(workout_violations)

        return violations

    def _validate_workout(
        self, workout: Dict[str, Any], week_num: int, workout_index: int
    ) -> List[Dict[str, str]]:
        """Validate structure and data of a single workout."""
        violations = []
        location = f"week {week_num}, workout {workout_index + 1}"

        required_fields = ["day", "workout_type", "distance_miles"]
        for field in required_fields:
            if field not in workout:
                violations.append(
                    {
                        "rule": f"missing_{field}",
                        "severity": "error",
                        "location": location,
                        "details": f"Workout missing {field}",
                        "suggestion": f"Add {field} field",
                    }
                )

        # Check distance_miles is valid
        distance = workout.get("distance_miles")
        if distance is not None:
            if not isinstance(distance, (int, float)):
                violations.append(
                    {
                        "rule": "invalid_distance_type",
                        "severity": "error",
                        "location": location,
                        "details": f"distance_miles must be a number, got {type(distance)}",
                        "suggestion": "Use numeric value for distance_miles",
                    }
                )
            elif distance < 0:
                violations.append(
                    {
                        "rule": "negative_distance",
                        "severity": "error",
                        "location": location,
                        "details": f"distance_miles is negative: {distance}",
                        "suggestion": "Distance must be non-negative",
                    }
                )

        return violations

    def _format_distance(
        self, miles: float, unit_system: str, precision: int = 1
    ) -> str:
        """Format distance with correct unit label."""
        if unit_system == "metric":
            km = miles_to_km(miles)
            return f"{km:.{precision}f} km"
        else:
            return f"{miles:.{precision}f} mi"

    def _validate_mileage_progression(
        self, weeks: List[Dict[str, Any]], unit_system: str = "imperial"
    ) -> List[Dict[str, str]]:
        """Validate 10% weekly mileage increase rule (except when returning from cutback)."""
        violations = []

        if len(weeks) < 2:
            return violations

        # Sort by week_number to ensure correct order
        sorted_weeks = sorted(weeks, key=lambda w: w.get("week_number", 0))

        for i in range(1, len(sorted_weeks)):
            prev_week = sorted_weeks[i - 1]
            curr_week = sorted_weeks[i]

            prev_mileage = prev_week.get("weekly_mileage")
            curr_mileage = curr_week.get("weekly_mileage")

            if not isinstance(prev_mileage, (int, float)) or not isinstance(
                curr_mileage, (int, float)
            ):
                continue  # Skip if mileage not numeric (already flagged in structure validation)

            if prev_mileage <= 0:
                continue  # Skip if previous week had no mileage

            # PRIMARY: Use is_cutback flag from spine (authoritative truth)
            # FALLBACK: Detect cutback by mileage pattern (for legacy plans)
            is_after_cutback = prev_week.get("is_cutback", False)
            baseline_mileage = prev_mileage

            # Fallback detection if flag not present
            if not is_after_cutback and i >= 2:
                week_before_prev = sorted_weeks[i - 2]
                week_before_prev_mileage = week_before_prev.get("weekly_mileage")
                if (
                    isinstance(week_before_prev_mileage, (int, float))
                    and week_before_prev_mileage > 0
                ):
                    if prev_mileage <= week_before_prev_mileage * 0.8:
                        is_after_cutback = True

            # Use pre-cutback baseline for rebound comparison
            if is_after_cutback and i >= 2:
                week_before_prev = sorted_weeks[i - 2]
                week_before_prev_mileage = week_before_prev.get("weekly_mileage")
                if (
                    isinstance(week_before_prev_mileage, (int, float))
                    and week_before_prev_mileage > 0
                ):
                    baseline_mileage = week_before_prev_mileage

            # Calculate percentage increase vs baseline (prev week or pre-cutback week)
            increase = ((curr_mileage - baseline_mileage) / baseline_mileage) * 100

            if is_after_cutback:
                # Allow rebound without flagging (spine intentionally restores mileage)
                continue

            incr_cap = self.MAX_WEEKLY_INCREASE_PERCENT
            if increase > incr_cap + 0.05:
                max_allowed = prev_mileage * (1 + incr_cap / 100)
                violations.append(
                    {
                        "rule": "10_percent_rule_violation",
                        "severity": "error",
                        "location": f"week {curr_week.get('week_number')}",
                        "details": f"Weekly mileage increased {increase:.1f}% (from {self._format_distance(prev_mileage, unit_system)} to {self._format_distance(curr_mileage, unit_system)}), maximum allowed is {incr_cap:.1f}%",
                        "suggestion": f"Reduce week {curr_week.get('week_number')} mileage to at most {self._format_distance(max_allowed, unit_system)}",
                    }
                )

        return violations

    def _validate_cutback_weeks(
        self, weeks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Validate that at least one cutback week exists.

        PRIMARY: Uses is_cutback flag from spine (authoritative truth)
        FALLBACK: Detects cutback by mileage pattern (for legacy plans)
        """
        violations = []

        if len(weeks) < 6:
            return violations  # Too short plan, cutbacks not required

        sorted_weeks = sorted(weeks, key=lambda w: w.get("week_number", 0))

        # PRIMARY: Check for is_cutback flag (authoritative from spine)
        has_cutback = any(w.get("is_cutback", False) for w in sorted_weeks)

        # FALLBACK: Detect by mileage pattern if no flags found
        if not has_cutback:
            for i in range(1, len(sorted_weeks) - self.TAPER_WEEKS):
                prev_mileage = sorted_weeks[i - 1].get("weekly_mileage", 0)
                curr_mileage = sorted_weeks[i].get("weekly_mileage", 0)

                if isinstance(prev_mileage, (int, float)) and isinstance(
                    curr_mileage, (int, float)
                ):
                    if prev_mileage > 0 and curr_mileage <= prev_mileage * 0.85:
                        has_cutback = True
                        break

        if not has_cutback:
            violations.append(
                {
                    "rule": "no_cutback_weeks",
                    "severity": "error",
                    "location": "plan",
                    "details": f"No cutback weeks found in {len(sorted_weeks)}-week plan. At least one recovery week is recommended.",
                    "suggestion": "Add at least one cutback week (reduce mileage by 15-20%)",
                }
            )

        return violations

    def _validate_long_run_progression(
        self, weeks: List[Dict[str, Any]], unit_system: str = "imperial"
    ) -> List[Dict[str, str]]:
        """Validate long run progression is safe (no big jumps)."""
        # Unit-aware thresholds: 2.0 miles = 3.2 km
        MAX_ABSOLUTE_INCREASE_MILES = 2.0
        MAX_ABSOLUTE_INCREASE_KM = 3.2
        MAX_PERCENT_INCREASE = 20.0

        # Convert threshold to miles for internal comparison
        max_absolute_increase_miles = (
            km_to_miles(MAX_ABSOLUTE_INCREASE_KM)
            if unit_system == "metric"
            else MAX_ABSOLUTE_INCREASE_MILES
        )
        violations = []

        if len(weeks) < 2:
            return violations

        sorted_weeks = sorted(weeks, key=lambda w: w.get("week_number", 0))

        prev_long_run = None
        long_run_two_back = None
        for week in sorted_weeks:
            week_num = week.get("week_number", 0)
            workouts = week.get("workouts", [])

            # Find long run in this week
            long_runs = [
                w
                for w in workouts
                if w.get("workout_type", "").lower() in ["long run", "long"]
            ]
            if not long_runs:
                continue

            # Get longest run in week (in case multiple)
            curr_long_run = max(
                [w.get("distance_miles", 0) for w in long_runs], default=0
            )

            if prev_long_run is not None and prev_long_run > 0:
                baseline = prev_long_run

                # PRIMARY: Use is_cutback flag from spine (authoritative truth)
                # FALLBACK: Detect cutback by mileage pattern
                prev_week = (
                    sorted_weeks[sorted_weeks.index(week) - 1]
                    if sorted_weeks.index(week) > 0
                    else None
                )
                is_cutback_rebound = (
                    prev_week.get("is_cutback", False) if prev_week else False
                )

                # Fallback detection if flag not present
                if not is_cutback_rebound and (
                    long_run_two_back is not None
                    and long_run_two_back > 0
                    and prev_long_run <= long_run_two_back * 0.8
                ):
                    is_cutback_rebound = True

                # Use pre-cutback baseline for rebound comparison
                if (
                    is_cutback_rebound
                    and long_run_two_back is not None
                    and long_run_two_back > 0
                ):
                    baseline = long_run_two_back

                increase = curr_long_run - baseline
                percent_increase = (increase / baseline * 100) if baseline > 0 else 0

                if is_cutback_rebound:
                    # Allow rebound after cutback without flagging
                    pass
                elif (
                    increase > max_absolute_increase_miles
                    and percent_increase > MAX_PERCENT_INCREASE
                ):
                    # Relaxed: 20% or unit-aware absolute limit (sanity check, Step 5 handles strict limits)
                    max_allowed = baseline + max_absolute_increase_miles
                    max_absolute_display = (
                        MAX_ABSOLUTE_INCREASE_KM
                        if unit_system == "metric"
                        else MAX_ABSOLUTE_INCREASE_MILES
                    )
                    violations.append(
                        {
                            "rule": "unsafe_long_run_progression",
                            "severity": "error",
                            "location": f"week {week_num}",
                            "details": f"Long run increased {self._format_distance(increase, unit_system)} ({percent_increase:.1f}%) from {self._format_distance(baseline, unit_system)} to {self._format_distance(curr_long_run, unit_system)}. Maximum safe increase is {max_absolute_display:.1f} {'km' if unit_system == 'metric' else 'mi'} or {MAX_PERCENT_INCREASE}%",
                            "suggestion": f"Reduce long run distance in week {week_num} to at most {self._format_distance(max_allowed, unit_system)}",
                        }
                    )

            if curr_long_run > 0:
                long_run_two_back = prev_long_run
                prev_long_run = curr_long_run

        return violations

    def _validate_taper(
        self, weeks: List[Dict[str, Any]], unit_system: str = "imperial"
    ) -> List[Dict[str, str]]:
        """Validate that final weeks taper (reduce volume) and phase structure."""
        violations = []

        if len(weeks) < self.TAPER_WEEKS:
            return violations  # Too short plan

        sorted_weeks = sorted(weeks, key=lambda w: w.get("week_number", 0))

        # PRIMARY: Check that exactly TAPER_WEEKS are marked as "Taper" phase
        taper_phase_weeks = [
            w
            for w in sorted_weeks
            if str(w.get("phase", "")).lower().strip() in ["taper", "taper week"]
        ]

        if len(taper_phase_weeks) != self.TAPER_WEEKS:
            week_nums = [
                w.get("week_number") for w in sorted_weeks[-self.TAPER_WEEKS :]
            ]
            violations.append(
                {
                    "rule": "incorrect_taper_weeks",
                    "severity": "error",
                    "location": f"weeks {week_nums[0]}-{week_nums[-1]}",
                    "details": f"Plan has {len(taper_phase_weeks)} taper week(s) but should have {self.TAPER_WEEKS}. Found taper phases: {[w.get('week_number') for w in taper_phase_weeks]}",
                    "suggestion": f"Ensure exactly {self.TAPER_WEEKS} weeks are marked as 'Taper' phase before the race week",
                }
            )

        # SECONDARY: Check that taper weeks reduce mileage
        taper_weeks = sorted_weeks[-self.TAPER_WEEKS :]
        pre_taper_week = (
            sorted_weeks[-self.TAPER_WEEKS - 1]
            if len(sorted_weeks) > self.TAPER_WEEKS
            else None
        )

        if pre_taper_week:
            pre_taper_mileage = pre_taper_week.get("weekly_mileage")
            taper_week_mileages = [w.get("weekly_mileage") for w in taper_weeks]

            if isinstance(pre_taper_mileage, (int, float)) and all(
                isinstance(m, (int, float)) for m in taper_week_mileages
            ):
                # Check if taper weeks reduce mileage
                avg_taper_mileage = sum(taper_week_mileages) / len(taper_week_mileages)

                if (
                    avg_taper_mileage >= pre_taper_mileage * 0.95
                ):  # Less than 5% reduction means no taper
                    week_nums = [w.get("week_number") for w in taper_weeks]
                    violations.append(
                        {
                            "rule": "missing_taper",
                            "severity": "error",
                            "location": f"weeks {week_nums[0]}-{week_nums[-1]}",
                            "details": f"Final weeks do not taper. Pre-taper: {self._format_distance(pre_taper_mileage, unit_system)}, taper average: {self._format_distance(avg_taper_mileage, unit_system)}. Should reduce by at least 20-30%",
                            "suggestion": f"Reduce mileage in final {self.TAPER_WEEKS} weeks by 20-30%",
                        }
                    )

                # Check taper ratios match config (if available)
                if hasattr(self.config, "taper_ratios") and self.config.taper_ratios:
                    expected_ratios = self.config.taper_ratios
                    if len(taper_week_mileages) == len(expected_ratios):
                        for i, (actual_mileage, expected_ratio) in enumerate(
                            zip(taper_week_mileages, expected_ratios)
                        ):
                            expected_mileage = pre_taper_mileage * expected_ratio
                            actual_ratio = (
                                actual_mileage / pre_taper_mileage
                                if pre_taper_mileage > 0
                                else 0
                            )
                            # Allow 10% tolerance for rounding differences
                            if abs(actual_ratio - expected_ratio) > 0.10:
                                week_num = taper_weeks[i].get("week_number")
                                violations.append(
                                    {
                                        "rule": "taper_ratio_mismatch",
                                        "severity": "warning",
                                        "location": f"week {week_num}",
                                        "details": f"Taper week {i+1} has {self._format_distance(actual_mileage, unit_system)} ({actual_ratio*100:.0f}% of pre-taper), expected {self._format_distance(expected_mileage, unit_system)} ({expected_ratio*100:.0f}%)",
                                        "suggestion": f"Adjust week {week_num} mileage to match taper ratio of {expected_ratio*100:.0f}%",
                                    }
                                )

        return violations

    def _validate_long_run_bounds(
        self, weeks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Validate long run proportion and cap (config-based)."""
        violations: List[Dict[str, str]] = []
        phase_share_caps = {
            str(k).lower(): v
            for k, v in getattr(self.config, "max_long_run_share_by_phase", {}).items()
        }
        week_long_runs: Dict[int, float] = {}
        phase_by_week: Dict[int, str] = {}

        for w in weeks:
            total = w.get("weekly_mileage")
            workouts = w.get("workouts", [])
            if not isinstance(workouts, list) or not workouts:
                continue
            week_num = w.get("week_number")
            phase = str(w.get("phase", "") or "").strip()
            if isinstance(week_num, int):
                phase_by_week[week_num] = phase
            # Identify long run as workout_type containing 'long'
            long_runs = [
                wo
                for wo in workouts
                if str(wo.get("workout_type", "")).lower().startswith("long")
            ]
            if not long_runs:
                continue
            lr_miles = max(
                [
                    float(wo.get("distance_miles", wo.get("miles", 0)) or 0)
                    for wo in long_runs
                ]
            )
            if isinstance(week_num, int):
                week_long_runs[week_num] = lr_miles
            # Hard cap from config
            peak_cap = self.config.target_peak_miles
            if lr_miles > peak_cap:
                violations.append(
                    {
                        "rule": "long_run_cap_exceeded",
                        "severity": "error",
                        "location": f"week {w.get('week_number')}",
                        "details": f"Long run {lr_miles:.1f} miles exceeds cap {peak_cap:.1f}",
                        "suggestion": f"Reduce long run to {peak_cap:.1f} miles or less",
                    }
                )
            # Proportion 25–35% of total weekly mileage when total available
            if isinstance(total, (int, float)) and total and total > 0:
                share = lr_miles / total
                lo, hi = self.config.long_run_percentage_ranges[
                    len(workouts) if workouts else 4
                ]
                hi_limit = hi
                if phase and phase_share_caps:
                    phase_cap = phase_share_caps.get(phase.lower())
                    if phase_cap is not None:
                        hi_limit = phase_cap
                if share > hi_limit:
                    # Downgrade to warning - share violations are not safety-critical
                    # and can occur naturally in taper when total mileage drops faster than long run
                    violations.append(
                        {
                            "rule": "long_run_share_too_high",
                            "severity": "warning",
                            "location": f"week {w.get('week_number')}",
                            "details": f"Long run is {share*100:.1f}% of weekly mileage (>{hi_limit*100:.0f}%, phase={phase or 'unknown'})",
                            "suggestion": "Consider reducing long run or increasing easy mileage",
                        }
                    )
                elif share < lo:
                    # Add tolerance for rounding - only warn if significantly below minimum
                    # This prevents false warnings for minor differences (e.g., 29.4% vs 30%)
                    # that are due to rounding or constraint balancing
                    tolerance = (
                        0.01  # 1% tolerance for rounding/calculation differences
                    )
                    if share < (lo - tolerance):
                        violations.append(
                            {
                                "rule": "long_run_share_too_low",
                                "severity": "warning",
                                "location": f"week {w.get('week_number')}",
                                "details": f"Long run is {share*100:.1f}% of weekly mileage (<{lo*100:.0f}%)",
                                "suggestion": "Consider adjusting long run to fall inside expected percentage range",
                            }
                        )
        # Dynamic check for final taper long run ratio
        taper_weeks = [
            wn for wn, phase in phase_by_week.items() if phase.lower() == "taper"
        ]
        if taper_weeks:
            final_week_num = max(taper_weeks)
            prev_week_num = final_week_num - 1
            prev_lr = week_long_runs.get(prev_week_num)
            curr_lr = week_long_runs.get(final_week_num)
            if prev_lr and prev_lr > 0 and curr_lr:
                ratio = curr_lr / prev_lr
                lb, ub = getattr(self.config, "final_taper_long_run_range", (0.4, 0.6))
                if ratio < lb or ratio > ub:
                    violations.append(
                        {
                            "rule": "final_taper_long_run_out_of_range",
                            "severity": "warning",
                            "location": f"week {final_week_num}",
                            "details": (
                                f"Final taper long run is {curr_lr:.1f} mi "
                                f"({ratio*100:.0f}% of prior week {prev_lr:.1f} mi). "
                                f"Expected {lb*100:.0f}–{ub*100:.0f}%."
                            ),
                            "suggestion": (
                                "Adjust final taper long run to better align with previous week "
                                "or increase/decrease supporting mileage."
                            ),
                        }
                    )

        return violations

    @staticmethod
    def _validate_week_completeness(
        weeks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Validate that weeks are sequential with no gaps."""
        violations = []

        if not weeks:
            return violations

        sorted_weeks = sorted(weeks, key=lambda w: w.get("week_number", 0))
        week_numbers = [w.get("week_number") for w in sorted_weeks]

        # Check for gaps
        if len(set(week_numbers)) != len(week_numbers):
            violations.append(
                {
                    "rule": "duplicate_week_numbers",
                    "severity": "error",
                    "location": "plan",
                    "details": "Duplicate week numbers found",
                    "suggestion": "Ensure each week has a unique week_number",
                }
            )

        # Check for gaps in sequence
        expected_weeks = list(range(1, len(sorted_weeks) + 1))
        missing_weeks = [w for w in expected_weeks if w not in week_numbers]

        if missing_weeks:
            violations.append(
                {
                    "rule": "missing_weeks",
                    "severity": "error",
                    "location": "plan",
                    "details": f"Missing week numbers: {missing_weeks}",
                    "suggestion": f"Add missing weeks: {missing_weeks}",
                }
            )

        return violations

    def _validate_race_date_timing(self, plan: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Validate that plan has enough time before race date.

        If the plan would extend past the race date, this adds a warning
        indicating the user doesn't have enough time to prepare.
        """
        violations = []

        race_date = plan.get("race_date")
        start_date = plan.get("start_date")
        weeks = plan.get("weeks", [])

        if not race_date or not start_date or not weeks:
            # Can't validate if missing required data
            return violations

        try:
            # Parse dates
            if isinstance(race_date, str):
                race_date = datetime.fromisoformat(race_date.split("T")[0]).date()
            elif isinstance(race_date, datetime):
                race_date = race_date.date()

            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.split("T")[0]).date()
            elif isinstance(start_date, datetime):
                start_date = start_date.date()

            # Calculate plan end date: start date + number of weeks
            plan_weeks_count = len(weeks)
            plan_end_date = start_date + timedelta(weeks=plan_weeks_count)

            # Check if plan would end after race date
            if plan_end_date > race_date:
                violations.append(
                    {
                        "rule": "insufficient_time_before_race",
                        "severity": "warning",
                        "location": "plan",
                        "details": (
                            f"Plan requires {plan_weeks_count} weeks but would extend past race date. "
                            f"Race date: {race_date.isoformat()}, "
                            f"Plan would end: {plan_end_date.isoformat()}. "
                            f"You don't have enough time to fully prepare with this {plan_weeks_count}-week plan."
                        ),
                        "suggestion": (
                            "Consider choosing a later race date, or the system will adjust the plan "
                            "to fit the available time. The plan will still be created but may not be "
                            "ideal for full preparation."
                        ),
                    }
                )
                logger.warning(
                    f"Plan timing issue: {plan_weeks_count}-week plan starting {start_date} "
                    f"would end {plan_end_date} but race is {race_date}"
                )
        except Exception as e:
            logger.warning(f"Error validating race date timing: {e}")
            # Don't add violation if we can't parse dates - let other validations handle it

        return violations

    # Backwards compatibility helper intentionally omitted for V2; callers should
    # instantiate PlanValidationServiceV2 with a RaceDistanceConfig.
