import re
from datetime import datetime, timedelta

import pytest

from src.services.training_plan.prompt_builder_service import PromptBuilderService


def _base_insights(
    data_quality="sufficient",
    ready_for_marathon=True,
):
    return {
        "current_fitness": {
            "weekly_mileage": 20.0,
            "longest_run": 10.0,
            "average_pace": "10:00/mile",
            "fitness_trend": "Stable",
        },
        "recommendations": {
            "starting_mileage": {
                "weekly_mileage": 20.0,
                "ready_for_marathon": ready_for_marathon,
                "confidence": "High",
            },
            "progression_rate": {"rate_percent": 10.0},
            "long_run_distance": {"distance": 12.0},
            "focus_areas": ["Base Building", "Injury Prevention"],
            "training_principles": ["10% rule"],
            "safety_guidelines": ["Be safe"],
        },
        "metadata": {
            "data_quality": data_quality,
            "calculated_at": datetime.now().isoformat(),
            "activities_analyzed": 10,
            "weeks_analyzed": 8,
        },
    }


def _base_user_profile():
    return {
        "age_group": "30-39",
        "height_feet": 5,
        "height_inches": 10,
        "weight": 165.0,
        "training_days": ["Mon", "Wed", "Fri"],
        "motivation": ["Health"],
    }


def _plan_request_with_race_date(days_from_now=140):
    return {
        "race_date": (datetime.now() + timedelta(days=days_from_now)).strftime(
            "%Y-%m-%d"
        ),
        "race_name": "Example Marathon",
        "race_location": "Example City",
        "primary_goal": "Just Finish",
        "training_days": ["Mon", "Wed", "Fri"],
        "notes": "N/A",
    }


class TestPromptBuilderService:
    def test_build_complete_prompt_basic_structure(self):
        insights = _base_insights()
        user_profile = _base_user_profile()
        plan_request = _plan_request_with_race_date()

        result = PromptBuilderService.build_complete_prompt(
            insights, user_profile, plan_request
        )

        # Top-level structure
        assert "messages" in result and isinstance(result["messages"], list)
        assert "config" in result and isinstance(result["config"], dict)
        assert "metadata" in result and isinstance(result["metadata"], dict)

        # Messages contain system and user
        roles = [m.get("role") for m in result["messages"]]
        assert "system" in roles and "user" in roles

        # Config defaults present
        assert result["config"]["model"]
        assert result["config"]["response_format"]["type"] == "json_object"
        assert isinstance(result["config"]["temperature"], (int, float))

        # Metadata propagated
        assert (
            result["metadata"]["data_quality"] == insights["metadata"]["data_quality"]
        )

        # User message contains key sections
        user_msg = next(m["content"] for m in result["messages"] if m["role"] == "user")
        for section in [
            "# RUNNER PROFILE",
            "# RACE GOAL",
            "# CURRENT FITNESS",
            "# TRAINING RECOMMENDATIONS",
            "# SCHEDULE CONSTRAINTS",
            "# YOUR TASK",
            "# OUTPUT FORMAT",
        ]:
            assert section in user_msg

    def test_weeks_until_race_calculation_in_user_message(self):
        insights = _base_insights()
        user_profile = _base_user_profile()
        # 56 days ≈ 8 weeks
        plan_request = _plan_request_with_race_date(days_from_now=56)

        result = PromptBuilderService.build_complete_prompt(
            insights, user_profile, plan_request
        )
        user_msg = next(m["content"] for m in result["messages"] if m["role"] == "user")

        # Expect the weeks line to indicate N weeks (avoid flakiness due to time-of-day)
        m = re.search(r"\((\d+) weeks available\)", user_msg)
        assert m is not None
        weeks = int(m.group(1))
        assert weeks >= 1

    def test_warning_when_time_less_than_16_weeks(self):
        insights = _base_insights()
        user_profile = _base_user_profile()
        # 8 weeks forces time constraint warning
        plan_request = _plan_request_with_race_date(days_from_now=56)

        result = PromptBuilderService.build_complete_prompt(
            insights, user_profile, plan_request
        )
        user_msg = next(m["content"] for m in result["messages"] if m["role"] == "user")

        assert "TIME CONSTRAINT" in user_msg

    def test_warning_when_data_quality_limited(self):
        insights = _base_insights(data_quality="limited")
        user_profile = _base_user_profile()
        plan_request = _plan_request_with_race_date(days_from_now=200)

        result = PromptBuilderService.build_complete_prompt(
            insights, user_profile, plan_request
        )
        user_msg = next(m["content"] for m in result["messages"] if m["role"] == "user")

        assert "LIMITED DATA" in user_msg

    def test_warning_when_not_ready_for_marathon(self):
        insights = _base_insights(ready_for_marathon=False)
        user_profile = _base_user_profile()
        plan_request = _plan_request_with_race_date(days_from_now=200)

        result = PromptBuilderService.build_complete_prompt(
            insights, user_profile, plan_request
        )
        user_msg = next(m["content"] for m in result["messages"] if m["role"] == "user")

        assert "BASE BUILDING NEEDED" in user_msg

    def test_output_format_section_has_required_keys(self):
        insights = _base_insights()
        user_profile = _base_user_profile()
        plan_request = _plan_request_with_race_date()

        result = PromptBuilderService.build_complete_prompt(
            insights, user_profile, plan_request
        )
        user_msg = next(m["content"] for m in result["messages"] if m["role"] == "user")

        # Simple checks for presence of JSON schema keys
        for key in [
            '"plan_name":',
            '"plan_summary":',
            '"weeks":',
            '"workouts":',
            '"race_week_strategy":',
            '"nutrition_tips":',
            '"injury_prevention_tips":',
        ]:
            assert key in user_msg

    def test_config_overrides(self, monkeypatch):
        insights = _base_insights()
        user_profile = _base_user_profile()
        plan_request = _plan_request_with_race_date()

        # Env defaults
        monkeypatch.setenv("TRAINING_PLAN_GPT_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("TRAINING_PLAN_GPT_TEMPERATURE", "0.3")

        # 1) Use env fallbacks when no overrides passed
        result_env = PromptBuilderService.build_complete_prompt(
            insights, user_profile, plan_request
        )
        assert result_env["config"]["model"] == "gpt-4o-mini"
        assert abs(result_env["config"]["temperature"] - 0.3) < 1e-6

        # 2) Explicit overrides take precedence over env
        result_over = PromptBuilderService.build_complete_prompt(
            insights,
            user_profile,
            plan_request,
            model="custom-model",
            temperature=0.15,
            response_format={"type": "json_object"},
        )
        assert result_over["config"]["model"] == "custom-model"
        assert abs(result_over["config"]["temperature"] - 0.15) < 1e-6
