"""Tests for plan workout taxonomy display helpers."""

from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
    taxonomy_pace_guidance,
    taxonomy_short_label,
)


def test_taxonomy_short_label_capitalizes_key():
    assert taxonomy_short_label("easy") == "Easy"
    assert taxonomy_short_label("long_run") == "Long_run"
    assert taxonomy_short_label("tempo") == "Tempo"


def test_taxonomy_pace_guidance_from_definition():
    assert taxonomy_pace_guidance("easy") == "Easy"
    assert taxonomy_pace_guidance("steady") == "Steady (comfortably moderate)"
    assert taxonomy_pace_guidance("tempo") == (
        "Tempo (comfortably hard, can speak in short phrases)"
    )


def test_taxonomy_helpers_default_for_empty():
    assert taxonomy_short_label("") == "Easy"
    assert taxonomy_pace_guidance("") == "Easy"
