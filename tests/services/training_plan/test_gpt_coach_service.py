import json
from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from src.services.training_plan.prompt_builder_service import PromptBuilderService


# Minimal JSON schema-like checker (avoid extra deps): required keys and invariants
def validate_plan_shape(plan: Dict[str, Any]) -> None:
    assert isinstance(plan, dict)
    for key in ["plan_name", "weeks"]:
        assert key in plan
    assert isinstance(plan["weeks"], list) and len(plan["weeks"]) > 0
    last_week = 0
    for w in plan["weeks"]:
        assert "week_number" in w and isinstance(w["week_number"], int)
        assert w["week_number"] > last_week
        last_week = w["week_number"]
        assert "workouts" in w and isinstance(w["workouts"], list)
        for wo in w["workouts"]:
            assert "day" in wo
            assert "workout_type" in wo
            assert "distance_miles" in wo and wo["distance_miles"] >= 0


@dataclass
class FakeLLMClient:
    responses: List[Any]
    calls: int = 0

    def completion(self, messages: List[Dict[str, str]], config: Dict[str, Any]) -> str:
        resp = self.responses[self.calls]
        self.calls += 1
        if isinstance(resp, Exception):
            raise resp
        return resp


def _fake_prompt():
    insights = {
        "current_fitness": {
            "weekly_mileage": 20,
            "longest_run": 10,
            "average_pace": "10:00/mile",
            "fitness_trend": "Stable",
        },
        "recommendations": {
            "starting_mileage": {
                "weekly_mileage": 20,
                "ready_for_marathon": True,
                "confidence": "High",
            },
            "progression_rate": {"rate_percent": 10.0},
            "long_run_distance": {"distance": 12.0},
            "focus_areas": ["Base Building"],
            "training_principles": ["10% rule"],
            "safety_guidelines": ["Be safe"],
        },
        "metadata": {"data_quality": "sufficient"},
    }
    profile = {
        "age_group": "30-39",
        "height_feet": 5,
        "height_inches": 10,
        "weight": 165.0,
        "training_days": ["Mon", "Wed", "Fri"],
        "motivation": ["Health"],
    }
    req = {
        "race_date": "2030-01-01",
        "primary_goal": "Just Finish",
        "marathon_experience": "First",
        "training_days": ["Mon", "Wed", "Fri"],
    }
    return PromptBuilderService.build_complete_prompt(insights, profile, req)


def _valid_plan_json() -> str:
    plan = {
        "plan_name": "Example Plan",
        "plan_summary": "Summary",
        "weeks": [
            {
                "week_number": 1,
                "phase": "Base Building",
                "weekly_mileage": 20.0,
                "week_notes": "",
                "workouts": [
                    {
                        "day": "Monday",
                        "workout_type": "Easy Run",
                        "distance_miles": 3.0,
                        "pace_guidance": "Easy",
                        "workout_description": "",
                    }
                ],
            }
        ],
        "race_week_strategy": "",
        "nutrition_tips": "",
        "injury_prevention_tips": "",
    }
    return json.dumps(plan)


def _malformed_json() -> str:
    return "{"  # broken


def _non_conforming_json() -> str:
    return json.dumps({"weeks": []})  # missing plan_name and no weeks


def _fenced_json() -> str:
    return """```json
{"plan_name":"Fenced","weeks":[{"week_number":1,"workouts":[{"day":"Mon","workout_type":"Easy Run","distance_miles":3.0}]}]}
```"""


def test_success_path(monkeypatch):
    from src.services.training_plan.gpt_coach_service import GptCoachService

    fake = FakeLLMClient([_valid_plan_json()])
    coach = GptCoachService(llm_client=fake, timeout_seconds=5, retries=0)
    prompt = _fake_prompt()
    plan = coach.generate_plan(prompt)
    validate_plan_shape(plan)


def test_retry_then_success(monkeypatch):
    from src.services.training_plan.gpt_coach_service import GptCoachService

    fake = FakeLLMClient([TimeoutError("t1"), _valid_plan_json()])
    coach = GptCoachService(llm_client=fake, timeout_seconds=1, retries=2)
    prompt = _fake_prompt()
    plan = coach.generate_plan(prompt)
    validate_plan_shape(plan)


def test_malformed_json_raises(monkeypatch):
    from src.services.training_plan.gpt_coach_service import GptCoachService

    fake = FakeLLMClient([_malformed_json()])
    coach = GptCoachService(llm_client=fake, timeout_seconds=5, retries=0)
    prompt = _fake_prompt()
    with pytest.raises(ValueError, match="invalid JSON"):
        coach.generate_plan(prompt)


def test_schema_violation_raises(monkeypatch):
    from src.services.training_plan.gpt_coach_service import GptCoachService

    fake = FakeLLMClient([_non_conforming_json()])
    coach = GptCoachService(llm_client=fake, timeout_seconds=5, retries=0)
    prompt = _fake_prompt()
    with pytest.raises(ValueError, match="schema"):
        coach.generate_plan(prompt)


def test_fenced_json_parsed(monkeypatch):
    from src.services.training_plan.gpt_coach_service import GptCoachService

    fake = FakeLLMClient([_fenced_json()])
    coach = GptCoachService(llm_client=fake, timeout_seconds=5, retries=0)
    prompt = _fake_prompt()
    plan = coach.generate_plan(prompt)
    validate_plan_shape(plan)


def test_factory_based_creation(monkeypatch):
    from src.services.training_plan.gpt_coach_service import GptCoachService

    monkeypatch.setenv("FAKE_LLM_JSON_RESPONSE", _valid_plan_json())
    coach = GptCoachService.create_default()
    prompt = _fake_prompt()
    plan = coach.generate_plan(prompt)
    validate_plan_shape(plan)
