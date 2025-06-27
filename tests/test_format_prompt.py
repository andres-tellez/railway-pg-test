import pytest
from src.utils.gpt_ops import format_prompt

def test_format_prompt_with_valid_data():
    user_question = "How far did I run this week?"
    activities = [
        {"date": "2025-06-24", "distance_km": 5.2, "duration_min": 28},
        {"date": "2025-06-25", "distance_km": 10.0, "duration_min": 54},
    ]

    result = format_prompt(user_question, activities)

    assert "You are a smart coaching assistant" in result
    assert "ACTIVITIES" in result
    assert "[1] date: 2025-06-24, distance_km: 5.2, duration_min: 28" in result
    assert "[2] date: 2025-06-25, distance_km: 10.0, duration_min: 54" in result
    assert "USER QUESTION" in result
    assert "How far did I run this week?" in result

def test_format_prompt_with_empty_activities():
    result = format_prompt("What's my performance?", [])
    assert "ACTIVITIES" in result
    assert "USER QUESTION" in result
    assert "What's my performance?" in result
