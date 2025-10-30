"""
Tests for Layer 5: Plan Validation Service

Tests safety rule enforcement and plan completeness validation.
"""

import pytest
from src.services.training_plan.plan_validation_service import PlanValidationService


def _valid_plan() -> dict:
    """Create a valid 16-week plan with proper progression."""
    weeks = []
    current_mileage = 20.0

    for week_num in range(1, 17):
        # Handle taper in final 3 weeks
        if week_num >= 14:
            phase = "Taper"
            if week_num == 14:
                # Start taper - reduce from previous week by 20%
                prev_mileage = weeks[-1]["weekly_mileage"] if weeks else current_mileage
                current_mileage = prev_mileage * 0.80
            elif week_num == 15:
                prev_mileage = weeks[-1]["weekly_mileage"]
                current_mileage = prev_mileage * 0.85  # Continue reducing
            else:  # week 16
                prev_mileage = weeks[-1]["weekly_mileage"]
                current_mileage = prev_mileage * 0.90  # Slight reduction
        elif week_num % 4 == 0:  # Cutback week every 4 weeks
            phase = "Base Building" if week_num < 8 else "Build"
            current_mileage = current_mileage * 0.75  # 25% reduction
        else:
            phase = "Base Building" if week_num < 8 else "Build"
            # Normal progression: increase by 10%
            current_mileage = current_mileage * 1.10

        week = {
            "week_number": week_num,
            "phase": phase,
            "weekly_mileage": round(current_mileage, 1),
            "week_notes": f"Week {week_num}",
            "workouts": [
                {
                    "day": "Monday",
                    "workout_type": "Easy Run",
                    "distance_miles": round(current_mileage / 4, 1),
                    "pace_guidance": "Easy",
                    "workout_description": "Easy recovery run",
                }
            ],
        }

        weeks.append(week)

    return {
        "plan_name": "Valid Plan",
        "plan_summary": "A valid training plan",
        "weeks": weeks,
        "race_week_strategy": "Taper guidance",
        "nutrition_tips": "Eat well",
        "injury_prevention_tips": "Stay healthy",
    }


def _plan_with_10_percent_violation() -> dict:
    """Plan that violates 10% rule (jumps from 20 to 25 mpw = 25% increase)."""
    plan = _valid_plan()
    plan["weeks"][0]["weekly_mileage"] = 20.0
    plan["weeks"][1]["weekly_mileage"] = 25.0  # 25% increase (should be max 22)
    return plan


def _plan_without_cutback() -> dict:
    """Plan missing cutback weeks."""
    plan = _valid_plan()
    # Remove cutbacks - all weeks increase
    base = 20.0
    for week in plan["weeks"]:
        week["weekly_mileage"] = round(base, 1)
        base = base * 1.10  # Always increasing, no cutback
    return plan


def _plan_with_invalid_long_run() -> dict:
    """Plan with long run that jumps too much (8 to 20 miles)."""
    plan = _valid_plan()
    # Week 1: 10 mile long run
    plan["weeks"][0]["workouts"].append(
        {
            "day": "Saturday",
            "workout_type": "Long Run",
            "distance_miles": 10.0,
            "pace_guidance": "Easy",
            "workout_description": "Long run",
        }
    )
    # Week 2: 20 mile long run (too big jump)
    plan["weeks"][1]["workouts"].append(
        {
            "day": "Saturday",
            "workout_type": "Long Run",
            "distance_miles": 20.0,
            "pace_guidance": "Easy",
            "workout_description": "Long run",
        }
    )
    return plan


def _plan_without_taper() -> dict:
    """Plan that doesn't taper (last weeks don't reduce)."""
    plan = _valid_plan()
    # Last 3 weeks should taper but keep increasing
    last_mileage = plan["weeks"][-4]["weekly_mileage"]
    for week in plan["weeks"][-3:]:
        week["weekly_mileage"] = last_mileage * 1.10  # Still increasing
        week["phase"] = "Peak"  # Wrong phase
    return plan


def _plan_with_negative_distance() -> dict:
    """Plan with invalid negative distance."""
    plan = _valid_plan()
    plan["weeks"][0]["workouts"][0]["distance_miles"] = -5.0
    return plan


def _plan_with_incomplete_weeks() -> dict:
    """Plan missing some weeks (gaps)."""
    plan = _valid_plan()
    # Remove week 8
    plan["weeks"] = [w for w in plan["weeks"] if w["week_number"] != 8]
    return plan


class TestPlanValidationService:
    def test_valid_plan_passes(self):
        plan = _valid_plan()
        result = PlanValidationService.validate_plan(plan)

        assert result["valid"] is True
        assert result["violations"] == []
        assert result["validated_plan"] is not None

    def test_10_percent_rule_violation(self):
        plan = _plan_with_10_percent_violation()
        result = PlanValidationService.validate_plan(plan)

        assert result["valid"] is False
        assert len(result["violations"]) > 0
        # Check that we have a 10% rule violation
        rules = [v.get("rule", "") for v in result["violations"]]
        assert "10_percent_rule_violation" in rules

    def test_missing_cutback_weeks(self):
        plan = _plan_without_cutback()
        result = PlanValidationService.validate_plan(plan)

        assert result["valid"] is False
        violations_text = " ".join([v["rule"] for v in result["violations"]])
        assert "cutback" in violations_text.lower()

    def test_invalid_long_run_progression(self):
        plan = _plan_with_invalid_long_run()
        result = PlanValidationService.validate_plan(plan)

        assert result["valid"] is False
        violations_text = " ".join([v["rule"] for v in result["violations"]])
        assert (
            "long run" in violations_text.lower()
            or "progression" in violations_text.lower()
        )

    def test_missing_taper(self):
        plan = _plan_without_taper()
        result = PlanValidationService.validate_plan(plan)

        assert result["valid"] is False
        violations_text = " ".join([v["rule"] for v in result["violations"]])
        assert "taper" in violations_text.lower()

    def test_negative_distance_rejected(self):
        plan = _plan_with_negative_distance()
        result = PlanValidationService.validate_plan(plan)

        assert result["valid"] is False
        violations_text = " ".join([v["rule"] for v in result["violations"]])
        assert (
            "negative" in violations_text.lower()
            or "invalid" in violations_text.lower()
        )

    def test_incomplete_weeks_detected(self):
        plan = _plan_with_incomplete_weeks()
        result = PlanValidationService.validate_plan(plan)

        assert result["valid"] is False
        violations_text = " ".join([v["rule"] for v in result["violations"]])
        assert (
            "missing" in violations_text.lower()
            or "gap" in violations_text.lower()
            or "complete" in violations_text.lower()
        )
