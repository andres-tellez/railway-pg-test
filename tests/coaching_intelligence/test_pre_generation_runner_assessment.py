from __future__ import annotations

from unittest.mock import MagicMock

from src.coaching_intelligence.pre_generation_runner_assessment import (
    SCHEMA_VERSION,
    PreGenerationRunnerAssessmentV1,
    build_pre_generation_runner_assessment,
)
from src.coaching_intelligence import pre_generation_runner_assessment as pgra


def test_alignment_disabled_omits_ambition_and_alignment(monkeypatch):
    monkeypatch.setattr(
        pgra,
        "compute_plan_intake_activity_summary",
        lambda **_kwargs: {"avg_miles_per_week_approx": 22.0},
    )
    monkeypatch.setattr(pgra, "_coach_memory_stats", lambda *_a, **_k: None)

    out = build_pre_generation_runner_assessment(
        MagicMock(),
        "11111111-1111-1111-1111-111111111111",
        plan_request={"primary_goal": "Target Time", "race_distance": "Marathon"},
        plan_intake_state={"draft": {}},
        alignment_enabled=False,
    )

    assert isinstance(out, PreGenerationRunnerAssessmentV1)
    assert out.schema_version == SCHEMA_VERSION
    assert out.ambition_gap is None
    assert out.intake_alignment_state is None
    assert out.activity_summary["avg_miles_per_week_approx"] == 22.0
    d = out.as_api_dict()
    assert "ambition_gap" not in d
    assert "intake_alignment_state" not in d
    assert d["activity_summary"]["avg_miles_per_week_approx"] == 22.0


def test_alignment_enabled_calls_evaluators_once(monkeypatch):
    monkeypatch.setattr(
        pgra,
        "compute_plan_intake_activity_summary",
        lambda **_kwargs: {
            "avg_miles_per_week_approx": 40.0,
            "longest_run_miles": 14.0,
        },
    )
    monkeypatch.setattr(pgra, "_coach_memory_stats", lambda *_a, **_k: None)

    calls = {"ambition": 0, "alignment": 0}

    def _amb(**_kwargs):
        calls["ambition"] += 1
        return {
            "stance": "COHERENT",
            "goal_demand": "TIME_TARGET",
            "baseline_band": "ESTABLISHED",
            "attributions": [],
        }

    def _align(**_kwargs):
        calls["alignment"] += 1
        return {
            "pause_required": False,
            "posture_state": "BALANCED",
            "unresolved_flags": [],
            "allowed_question_categories": [],
            "generation_ready": True,
            "attributions": [],
            "question_count": 0,
        }

    monkeypatch.setattr(pgra, "evaluate_ambition_gap", _amb)
    monkeypatch.setattr(pgra, "evaluate_intake_alignment_state", _align)

    out = build_pre_generation_runner_assessment(
        MagicMock(),
        "22222222-2222-2222-2222-222222222222",
        plan_request={
            "primary_goal": "Target Time",
            "target_time": "3:15:00",
            "race_distance": "Marathon",
        },
        plan_intake_state={"draft": {"primary_goal": "Target Time"}},
        alignment_enabled=True,
    )

    assert calls["ambition"] == 1
    assert calls["alignment"] == 1
    assert out.ambition_gap is not None
    assert out.intake_alignment_state is not None
    assert out.intake_alignment_state["generation_ready"] is True
    api = out.as_api_dict()
    assert api["ambition_gap"]["stance"] == "COHERENT"
    assert api["intake_alignment_state"]["generation_ready"] is True
