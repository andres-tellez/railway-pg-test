from __future__ import annotations

from src.coaching_intelligence.intake_alignment import evaluate_intake_alignment_state


def test_coherent_path_has_no_pause_and_is_ready():
    out = evaluate_intake_alignment_state(
        ambition_stance="COHERENT",
        primary_goal="Target Time",
    )
    assert out["pause_required"] is False
    assert out["generation_ready"] is True
    assert out["allowed_question_categories"] == []


def test_high_tension_path_requires_core_questions():
    out = evaluate_intake_alignment_state(
        ambition_stance="HIGH_TENSION",
        primary_goal="Target Time",
    )
    assert out["pause_required"] is True
    assert out["generation_ready"] is False
    assert out["unresolved_flags"] == ["frequency_flexibility"]
    assert out["allowed_question_categories"] == ["frequency_flexibility"]


def test_bounded_question_behavior_adds_optional_timeline_only_when_needed():
    out = evaluate_intake_alignment_state(
        ambition_stance="HIGH_TENSION",
        primary_goal="Target Time",
        frequency_flexible=False,
        posture_priority="durability",
    )
    assert out["pause_required"] is True
    assert out["generation_ready"] is False
    assert out["unresolved_flags"] == ["timeline_flexibility"]
    assert out["allowed_question_categories"] == ["timeline_flexibility"]


def test_idempotence_same_input_same_output():
    kwargs = {
        "ambition_stance": "MANAGEABLE_TENSION",
        "primary_goal": "Target Time",
        "frequency_flexible": True,
        "posture_priority": "balanced",
        "question_count": 1,
    }
    a = evaluate_intake_alignment_state(**kwargs)
    b = evaluate_intake_alignment_state(**kwargs)
    assert a == b


def test_generation_readiness_transitions_after_answers():
    before = evaluate_intake_alignment_state(
        ambition_stance="MANAGEABLE_TENSION",
        primary_goal="Target Time",
    )
    after_explicit = evaluate_intake_alignment_state(
        ambition_stance="MANAGEABLE_TENSION",
        primary_goal="Target Time",
        frequency_flexible=True,
        posture_priority="performance",
    )
    after_inferred = evaluate_intake_alignment_state(
        ambition_stance="MANAGEABLE_TENSION",
        primary_goal="Target Time",
        frequency_flexible=True,
    )
    assert before["generation_ready"] is False
    assert after_explicit["generation_ready"] is True
    assert after_explicit["posture_state"] == "PERFORMANCE_LEANING"
    assert after_inferred["generation_ready"] is True
    assert after_inferred["posture_state"] == "PERFORMANCE_LEANING"
    assert "RULE_ALIGNMENT_POSTURE_INFERRED" in after_inferred["attributions"]


def test_question_cap_enforcement_forces_resolved_state():
    out = evaluate_intake_alignment_state(
        ambition_stance="HIGH_TENSION",
        primary_goal="Target Time",
        question_count=3,
    )
    assert out["pause_required"] is True
    assert out["generation_ready"] is True
    assert out["posture_state"] == "BALANCED"
    assert out["unresolved_flags"] == []
    assert out["allowed_question_categories"] == []
    assert "RULE_ALIGNMENT_QUESTION_CAP_REACHED" in out["attributions"]
