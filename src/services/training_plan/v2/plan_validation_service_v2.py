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

logger = logging.getLogger(__name__)


class PlanValidationServiceV2:
    """Service for validating training plan safety and correctness."""

    def __init__(
        self,
        config: RaceDistanceConfig,
        max_weekly_increase_percent: float = 10.0,
        cutback_interval_weeks: int = 4,
    ) -> None:
        self.config = config
        self.MAX_WEEKLY_INCREASE_PERCENT = max_weekly_increase_percent
        self.CUTBACK_INTERVAL_WEEKS = cutback_interval_weeks
        self.TAPER_WEEKS = config.taper_weeks  # final taper weeks from config

    def validate_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate complete training plan against safety rules.

        Args:
            plan: Generated plan from Layer 4 GptCoachService

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
        violations.extend(self._validate_mileage_progression(weeks))
        violations.extend(self._validate_cutback_weeks(weeks))
        violations.extend(self._validate_long_run_progression(weeks))
        violations.extend(self._validate_taper(weeks))
        violations.extend(self._validate_long_run_bounds(weeks))
        violations.extend(self._validate_week_completeness(weeks))
        violations.extend(self._validate_race_date_timing(plan))

        # Check if there are any ERROR-level violations
        errors = [v for v in violations if v.get("severity") == "error"]
        is_valid = len(errors) == 0

        return {
            "valid": is_valid,
            "violations": violations,
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
                    total = sum(
                        float(w.get("distance_miles", w.get("miles", 0)) or 0)
                        for w in workouts_for_sum
                    )
                    week["weekly_mileage"] = round(total, 1)
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

    def _validate_mileage_progression(
        self, weeks: List[Dict[str, Any]]
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

            # Check if previous week was a deliberate cutback (>20% drop)
            is_after_cutback = False
            baseline_mileage = prev_mileage
            if i >= 2:
                week_before_prev = sorted_weeks[i - 2]
                week_before_prev_mileage = week_before_prev.get("weekly_mileage")
                if (
                    isinstance(week_before_prev_mileage, (int, float))
                    and week_before_prev_mileage > 0
                ):
                    if prev_mileage <= week_before_prev_mileage * 0.8:
                        is_after_cutback = True
                        baseline_mileage = week_before_prev_mileage

            # Calculate percentage increase vs baseline (prev week or pre-cutback week)
            increase = ((curr_mileage - baseline_mileage) / baseline_mileage) * 100

            if is_after_cutback:
                # Allow rebound without flagging (spine intentionally restores mileage)
                continue

            incr_cap = self.MAX_WEEKLY_INCREASE_PERCENT
            if increase > incr_cap + 0.05:
                violations.append(
                    {
                        "rule": "10_percent_rule_violation",
                        "severity": "error",
                        "location": f"week {curr_week.get('week_number')}",
                        "details": f"Weekly mileage increased {increase:.1f}% (from {prev_mileage} to {curr_mileage}), maximum allowed is {incr_cap:.1f}%",
                        "suggestion": f"Reduce week {curr_week.get('week_number')} mileage to at most {prev_mileage * (1 + incr_cap/100):.1f} miles",
                    }
                )

        return violations

    def _validate_cutback_weeks(
        self, weeks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Validate that cutback weeks exist every cutback_interval_weeks."""
        violations = []

        if len(weeks) < self.CUTBACK_INTERVAL_WEEKS:
            return violations  # Too short plan, cutbacks not required

        sorted_weeks = sorted(weeks, key=lambda w: w.get("week_number", 0))

        # Check for cutbacks every 3-4 weeks (skip first week)
        expected_cutback_weeks = []
        for i in range(
            self.CUTBACK_INTERVAL_WEEKS, len(sorted_weeks), self.CUTBACK_INTERVAL_WEEKS
        ):
            expected_cutback_weeks.append(i)

        found_cutbacks = 0
        for i in range(1, len(sorted_weeks)):
            if i < len(sorted_weeks) - 1:  # Not the last week
                prev_week = sorted_weeks[i - 1]
                curr_week = sorted_weeks[i]

                prev_mileage = prev_week.get("weekly_mileage")
                curr_mileage = curr_week.get("weekly_mileage")

                if isinstance(prev_mileage, (int, float)) and isinstance(
                    curr_mileage, (int, float)
                ):
                    # Cutback is a decrease of 20-30%
                    if prev_mileage > 0 and curr_mileage < prev_mileage * 0.80:
                        found_cutbacks += 1

        # Require at least one cutback for plans 8+ weeks
        if len(sorted_weeks) >= 8 and found_cutbacks == 0:
            violations.append(
                {
                    "rule": "missing_cutback_weeks",
                    "severity": "error",
                    "location": "plan",
                    "details": f"No cutback weeks found in {len(sorted_weeks)}-week plan. Should have cutbacks every 3-4 weeks",
                    "suggestion": "Add cutback weeks (reduce mileage by 20-30%) every 3-4 weeks",
                }
            )

        return violations

    def _validate_long_run_progression(
        self, weeks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Validate long run progression is safe (no big jumps)."""
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
                is_cutback_rebound = False
                if (
                    long_run_two_back is not None
                    and long_run_two_back > 0
                    and prev_long_run <= long_run_two_back * 0.8
                ):
                    # Previous week was a cutback; compare against week before it
                    baseline = long_run_two_back
                    is_cutback_rebound = True

                increase = curr_long_run - baseline
                percent_increase = (increase / baseline * 100) if baseline > 0 else 0

                if is_cutback_rebound:
                    # Allow rebound after cutback without flagging
                    pass
                elif increase > 1.0 and percent_increase > 10:
                    violations.append(
                        {
                            "rule": "unsafe_long_run_progression",
                            "severity": "error",
                            "location": f"week {week_num}",
                            "details": f"Long run increased {increase:.1f} miles ({percent_increase:.1f}%) from {baseline} to {curr_long_run}. Maximum safe increase is 1 mile or 10%",
                            "suggestion": f"Reduce long run distance in week {week_num} to at most {baseline + 1.0:.1f} miles",
                        }
                    )

            if curr_long_run > 0:
                long_run_two_back = prev_long_run
                prev_long_run = curr_long_run

        return violations

    def _validate_taper(self, weeks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Validate that final weeks taper (reduce volume)."""
        violations = []

        if len(weeks) < self.TAPER_WEEKS:
            return violations  # Too short plan

        sorted_weeks = sorted(weeks, key=lambda w: w.get("week_number", 0))

        # Check last 3 weeks
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
                            "details": f"Final weeks do not taper. Pre-taper: {pre_taper_mileage} mpw, taper average: {avg_taper_mileage:.1f} mpw. Should reduce by at least 20-30%",
                            "suggestion": f"Reduce mileage in final {self.TAPER_WEEKS} weeks by 20-30%",
                        }
                    )

        return violations

    @staticmethod
    def _validate_weekly_caps(weeks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Deprecated: previously enforced a hard weekly cap. No longer used."""
        return []

    def _validate_long_run_bounds(
        self, weeks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Validate long run proportion and cap (config-based)."""
        violations: List[Dict[str, str]] = []
        for w in weeks:
            total = w.get("weekly_mileage")
            workouts = w.get("workouts", [])
            if not isinstance(workouts, list) or not workouts:
                continue
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
                if share > hi:
                    violations.append(
                        {
                            "rule": "long_run_share_too_high",
                            "severity": "error",
                            "location": f"week {w.get('week_number')}",
                            "details": f"Long run is {share*100:.1f}% of weekly mileage (>{hi*100:.0f}%)",
                            "suggestion": "Reduce long run or increase easy mileage to keep long run within expected range",
                        }
                    )
                elif share < lo:
                    violations.append(
                        {
                            "rule": "long_run_share_too_low",
                            "severity": "warning",
                            "location": f"week {w.get('week_number')}",
                            "details": f"Long run is {share*100:.1f}% of weekly mileage (<{lo*100:.0f}%)",
                            "suggestion": "Consider adjusting long run to fall inside expected percentage range",
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
