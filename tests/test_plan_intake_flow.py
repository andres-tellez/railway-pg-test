from __future__ import annotations

from src.smartcoach_mobile_coach.plan_intake_flow import (
    PLAN_UX_STAGE_CONFIRM,
    PLAN_UX_STAGE_FAST_TRACK,
    PLAN_UX_STAGE_GOAL_ALIGNMENT,
    alignment_pause_coaching_facts_system_section,
    build_core_structured_ui_prompt,
    build_plan_request_from_state,
    format_plan_intake_confirmation_message,
    mark_plan_runner_understanding_shown,
    plan_intake_premature_confirmation_reply,
    plan_runner_understanding_shown,
    update_plan_intake_state,
    user_confirms_plan_intake,
)
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
)


def test_plan_intake_missing_required_order_for_empty_draft():
    state = update_plan_intake_state(None)
    assert state["missing_required"] == [
        "race_distance",
        "race_date",
        "primary_goal",
        "training_days",
    ]
    assert state["ux"]["stage"] == "understand_runner"


def test_structured_core_skips_nl_race_date_from_user_message():
    state = update_plan_intake_state(
        None,
        updates={"race_distance": "Marathon"},
        source_user_message="October 11, 2026",
    )
    assert state["draft"].get("race_date") is None


def test_build_core_structured_ui_prompt_race_distance_when_collecting():
    state = update_plan_intake_state(None)
    prompt = build_core_structured_ui_prompt(state)
    assert prompt is not None
    assert prompt["field_key"] == "plan_intake.race_distance"
    assert prompt["control_type"] == "single_select_chips"
    assert any(
        o.get("updates", {}).get("race_distance") == "Marathon"
        for o in (prompt.get("options") or [])
        if isinstance(o, dict)
    )


def test_build_core_structured_ui_prompt_target_time_includes_340_chip():
    """Coach often recommends ~3:40 — core intake chips must include it (matches goal_adjustment)."""
    state = update_plan_intake_state(
        None,
        updates={
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "training_days": ["Mon", "Wed", "Sat"],
        },
    )
    assert state["missing_required"][0] == "target_time"
    prompt = build_core_structured_ui_prompt(state)
    assert prompt is not None
    assert prompt["field_key"] == "plan_intake.target_time"
    by_label = {
        str(o.get("label")): o
        for o in (prompt.get("options") or [])
        if isinstance(o, dict) and o.get("label")
    }
    assert "3:40" in by_label
    assert by_label["3:40"].get("updates", {}).get("target_time") == "3:40:00"


def test_alignment_state_refreshes_after_frequency_structured_answer(monkeypatch):
    base = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-11",
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Mon", "Tue", "Sun"],
        },
    )
    _ag_attr = synthetic_ambition_attributions(
        baseline_band="THIN",
        goal_demand="TIME_TARGET",
        thin_baseline_data=False,
        longest_run_miles=8.0,
    )
    stale_alignment = {
        "enabled": True,
        "ambition_stance": "HIGH_TENSION",
        "ambition_attributions": list(_ag_attr),
        "baseline_band": "THIN",
        "goal_demand": "TIME_TARGET",
        "answers": {},
        "asked_categories": [],
        "question_count": 0,
        "state": {
            "pause_required": True,
            "generation_ready": False,
            "unresolved_flags": ["frequency_flexibility"],
            "allowed_question_categories": [
                "frequency_flexibility",
            ],
            "posture_state": "UNRESOLVED",
            "attributions": [],
            "question_count": 0,
        },
        "attributions": list(_ag_attr),
    }
    base["alignment"] = stale_alignment
    out = update_plan_intake_state(
        base,
        updates={"alignment_frequency_flexible": True},
    )
    inner = (out.get("alignment") or {}).get("state") or {}
    assert "frequency_flexibility" not in (inner.get("unresolved_flags") or [])
    assert inner.get("generation_ready") is True
    assert inner.get("posture_state") == "PERFORMANCE_LEANING"
    assert (out.get("alignment") or {}).get("answers", {}).get("posture_priority") == (
        "PERFORMANCE_LEANING"
    )
    assert (inner.get("allowed_question_categories") or []) == []


def test_alignment_pause_coaching_facts_section_when_paused():
    intake = {
        "draft": {
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Mon", "Tue", "Sun"],
        },
        "alignment": {
            "ambition_stance": "HIGH_TENSION",
            "baseline_band": "THIN",
            "goal_demand": "TIME_TARGET",
            "state": {
                "pause_required": True,
                "generation_ready": False,
                "allowed_question_categories": ["frequency_flexibility"],
            },
        },
    }
    text = alignment_pause_coaching_facts_system_section(intake)
    assert "HIGH_TENSION" in text
    assert "frequency_flexibility" in text


def test_plan_intake_updates_to_ready_state():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
    )
    assert state["ready_to_generate"] is True
    assert state["status"] == "ready_to_confirm"
    assert state["draft"]["long_run_day"] == "Sat"
    assert state["missing_required"] == []
    assert state["ux"]["stage"] == PLAN_UX_STAGE_FAST_TRACK


def test_plan_intake_rejects_bad_training_days():
    state = update_plan_intake_state(
        None,
        updates={
            "training_days": ["Tue", "Funday"],
        },
    )
    assert state["ready_to_generate"] is False
    assert any("training_days" in e for e in state["errors"])


def test_plan_intake_target_time_required_for_target_goal():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
            "training_days": "Tue,Thu,Sat",
        },
    )
    assert "target_time" in state["missing_required"]
    assert state["ready_to_generate"] is False
    assert state["ux"]["stage"] == "details"


def test_missing_required_orders_target_time_before_training_days():
    """Clock goal should be collected immediately after goal type, not after schedule."""
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
        },
    )
    assert state["missing_required"] == ["target_time", "training_days"]


def test_plan_intake_ux_stage_goal_alignment_after_distance_only():
    state = update_plan_intake_state(None, updates={"race_distance": "Marathon"})
    assert state["ux"]["stage"] == PLAN_UX_STAGE_GOAL_ALIGNMENT


def test_plan_intake_ux_state_preserves_runner_understanding_flag():
    state = update_plan_intake_state(None, updates={"race_distance": "Marathon"})
    state = mark_plan_runner_understanding_shown(state)
    assert plan_runner_understanding_shown(state) is True

    state = update_plan_intake_state(state, updates={"race_date": "2026-10-12"})
    assert plan_runner_understanding_shown(state) is True


def test_plan_intake_mark_runner_understanding_advances_empty_stage():
    state = update_plan_intake_state(None)
    assert state["ux"]["stage"] == "understand_runner"

    state = mark_plan_runner_understanding_shown(state)
    assert state["ux"]["runner_understanding_shown"] is True
    assert state["ux"]["stage"] == PLAN_UX_STAGE_GOAL_ALIGNMENT


def test_plan_intake_ready_after_prior_draft_moves_to_confirm_stage():
    state = update_plan_intake_state(None, updates={"race_distance": "Marathon"})
    state = update_plan_intake_state(
        state,
        updates={
            "race_date": "2026-10-12",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
    )
    assert state["ready_to_generate"] is True
    assert state["ux"]["stage"] == PLAN_UX_STAGE_CONFIRM


def test_plan_intake_normalizes_goal_phrases():
    """Broader primary_goal strings map to schema enum values."""
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "going for a personal record",
            "training_days": ["Tue", "Thu", "Sat"],
            "target_time": "3:40:00",
        },
    )
    assert state["draft"]["primary_goal"] == "Target Time"
    assert state["ready_to_generate"] is True


def test_build_plan_request_from_state_validates_schema():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
            "long_run_day": "Sat",
            "notes": "Returning from injury, build conservatively.",
        },
    )
    req = build_plan_request_from_state(state)
    assert req["race_distance"] == "Marathon"
    assert req["long_run_day"] == "Sat"
    assert req["training_days"] == ["Tue", "Thu", "Sat"]


def test_plan_intake_accepts_natural_language_race_date():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "October 11 of 2026",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        },
    )
    assert state["draft"]["race_date"] == "2026-10-11"
    assert state["ready_to_generate"] is True


def test_plan_intake_target_time_from_spoken_duration():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
            "target_time": "3 hours 40 minutes",
            "training_days": ["Tue", "Thu", "Sat"],
        },
    )
    assert state["draft"]["target_time"] == "3:40:00"
    assert state["ready_to_generate"] is True


def test_plan_intake_training_days_monday_through_saturday_string():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": "Monday through Saturday",
        },
    )
    assert state["draft"]["training_days"] == [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
    ]
    assert state["ready_to_generate"] is True


def test_plan_intake_training_days_weekdays_plus_saturday():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": "weekdays plus Saturday",
        },
    )
    assert state["draft"]["training_days"] == [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
    ]


def test_plan_intake_training_days_count_is_valid_partial_input():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
            "target_time": "3:30:00",
            "training_days": "5 days per week",
        },
    )
    assert state["ready_to_generate"] is False
    assert state["errors"] == []
    assert state["missing_required"] == ["training_days"]
    assert state["ux"]["training_days_count"] == 5
    assert state["ux"]["stage"] == "details"
    assert "training_days" not in state["draft"]
    assert state["draft"]["race_distance"] == "Marathon"
    assert state["draft"]["target_time"] == "3:30:00"


def test_plan_intake_training_days_actual_weekdays_clear_count_partial():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": "5 days per week",
        },
    )
    state = update_plan_intake_state(
        state,
        updates={"training_days": "Monday, Tuesday, Thursday, Friday, Saturday"},
    )
    assert state["ready_to_generate"] is True
    assert state["ux"]["stage"] == PLAN_UX_STAGE_CONFIRM
    assert "training_days_count" not in state["ux"]
    assert state["draft"]["training_days"] == ["Mon", "Tue", "Thu", "Fri", "Sat"]


def test_plan_intake_training_days_wraparound_range():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": "Friday through Monday",
        },
    )
    assert state["draft"]["training_days"] == ["Fri", "Sat", "Sun", "Mon"]


def test_plan_intake_infers_marathon_from_race_name_only():
    state = update_plan_intake_state(
        None,
        updates={
            "race_name": "Chicago Marathon",
            "race_date": "2026-10-12",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
    )
    assert state["draft"]["race_distance"] == "Marathon"
    assert state["draft"]["race_name"] == "Chicago Marathon"
    assert state["ready_to_generate"] is True


def test_plan_intake_normalizes_race_distance_synonyms():
    state = update_plan_intake_state(
        None,
        updates={"race_distance": "full marathon"},
    )
    assert state["draft"]["race_distance"] == "Marathon"


def test_plan_intake_fills_race_name_from_source_user_message():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
        source_user_message=(
            "Please build a plan for the Bank of America Chicago Marathon on that date."
        ),
    )
    assert state["draft"]["race_name"] == "Bank of America Chicago Marathon"
    assert state["ready_to_generate"] is True


def test_plan_intake_does_not_overwrite_explicit_race_name_when_user_message_differs():
    state = update_plan_intake_state(
        None,
        updates={
            "race_name": "Berlin Marathon",
            "race_date": "2026-09-27",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
        source_user_message="I was also thinking about Chicago Marathon someday",
    )
    assert state["draft"]["race_name"] == "Berlin Marathon"


def test_plan_intake_premature_confirmation_reply_with_days_per_week_count_only():
    state = update_plan_intake_state(
        None,
        updates={
            "race_distance": "Marathon",
            "race_name": "Chicago Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:40",
            "training_days": "6 days a week",
        },
    )
    assert state["ready_to_generate"] is False
    assert "training_days" in state["missing_required"]
    assert state["ux"].get("training_days_count") == 6
    text = plan_intake_premature_confirmation_reply(state)
    assert "6" in text
    assert "week" in text.lower()


def test_user_confirms_plan_intake_short_affirmations():
    assert user_confirms_plan_intake("Y") is True
    assert user_confirms_plan_intake("y.") is True
    assert user_confirms_plan_intake("yes") is True
    assert user_confirms_plan_intake("Looks good!") is True
    assert user_confirms_plan_intake("yes but change the date") is False
    assert user_confirms_plan_intake("no thanks") is False


def test_user_confirms_plan_intake_rejects_compound_yes_answers():
    """'Yes. Saturdays' answers long-run day — must not count as generate confirm."""
    assert user_confirms_plan_intake("Yes. Saturdays") is False
    assert user_confirms_plan_intake("Yes, Monday through Friday") is False
    assert user_confirms_plan_intake("Yes please use Saturday") is False


def test_plan_intake_parses_hyphen_weekday_range_mon_sat():
    state = update_plan_intake_state(
        None,
        updates={"training_days": "Mon-Sat"},
    )
    assert state["draft"]["training_days"] == [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
    ]


def test_plan_intake_infers_alignment_frequency_flexible_from_user_message():
    state = update_plan_intake_state(
        {
            "draft": {
                "race_distance": "Marathon",
                "race_date": "2026-10-11",
                "primary_goal": "Target Time",
                "target_time": "3:00:00",
                "training_days": ["Thu", "Sat"],
            },
            "alignment": {},
        },
        updates={},
        source_user_message="Add another day. Make it Tue.",
    )
    assert state["alignment"]["answers"]["frequency_flexible"] is True


def test_plan_intake_does_not_override_explicit_alignment_updates_with_message_parse():
    state = update_plan_intake_state(
        {"draft": {}, "alignment": {}},
        updates={"alignment_frequency_flexible": False},
        source_user_message="I can add another day if needed",
    )
    assert state["alignment"]["answers"]["frequency_flexible"] is False


def test_frequency_flexible_true_sets_expansion_pending_and_missing_training_days():
    state = update_plan_intake_state(
        {
            "draft": {
                "race_distance": "Marathon",
                "race_date": "2026-10-11",
                "primary_goal": "Target Time",
                "target_time": "3:00:00",
                "training_days": ["Mon", "Tue", "Sun"],
            },
            "alignment": {},
        },
        updates={"alignment_frequency_flexible": True},
    )
    assert state["ux"].get("training_days_expansion_pending") is True
    assert "training_days" in state["missing_required"]
    assert state["ready_to_generate"] is False


def test_training_days_commit_clears_expansion_pending():
    base = update_plan_intake_state(
        {
            "draft": {
                "race_distance": "Marathon",
                "race_date": "2026-10-11",
                "primary_goal": "Target Time",
                "target_time": "3:00:00",
                "training_days": ["Mon", "Tue", "Sun"],
            },
            "alignment": {},
        },
        updates={"alignment_frequency_flexible": True},
    )
    assert base["ux"].get("training_days_expansion_pending") is True
    nxt = update_plan_intake_state(
        base,
        updates={"training_days": ["Mon", "Wed", "Thu", "Sat"]},
    )
    assert nxt["ux"].get("training_days_expansion_pending") is not True
    assert nxt["ux"].get("schedule_confirm_before_posture") is True


def test_schedule_confirm_yes_clears_pending():
    st = update_plan_intake_state(
        {
            "draft": {
                "race_distance": "Marathon",
                "race_date": "2026-10-11",
                "primary_goal": "Target Time",
                "target_time": "3:00:00",
                "training_days": ["Mon", "Wed", "Thu", "Sat"],
            },
            "alignment": {},
            "ux": {"schedule_confirm_before_posture": True},
        },
        updates={"schedule_days_confirmed": True},
    )
    assert st["ux"].get("schedule_confirm_before_posture") is not True


def test_schedule_confirm_no_reopens_training_days():
    st = update_plan_intake_state(
        {
            "draft": {
                "race_distance": "Marathon",
                "race_date": "2026-10-11",
                "primary_goal": "Target Time",
                "target_time": "3:00:00",
                "training_days": ["Mon", "Wed", "Thu", "Sat"],
            },
            "alignment": {},
            "ux": {"schedule_confirm_before_posture": True},
        },
        updates={"schedule_days_confirmed": False},
    )
    assert st["ux"].get("schedule_confirm_before_posture") is not True
    assert st["ux"].get("training_days_expansion_pending") is True
    assert "training_days" in st["missing_required"]


def test_ready_to_generate_false_until_alignment_resolved():
    s0 = update_plan_intake_state(
        None,
        updates={
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Mon", "Tue", "Wed", "Thu"],
        },
    )
    assert s0["ready_to_generate"] is True
    s1 = update_plan_intake_state(
        {
            **s0,
            "alignment": {
                "ambition_stance": "HIGH_TENSION",
                "answers": {},
            },
        },
        updates={},
    )
    assert s1["ready_to_generate"] is False
    assert s1["status"] == "collecting"


def test_apply_coach_suggested_goal_updates_time_and_advances_past_review(monkeypatch):
    """Runner-analysis 'Set goal around X' applies time and moves on without re-review loop."""
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")
    base = update_plan_intake_state(
        None,
        updates={
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Mon", "Wed", "Sat"],
        },
    )
    base["ux"]["intake_confirmed"] = True
    base["ux"]["runner_review_delivered"] = True
    base["ux"]["plan_generation_confirmed"] = True

    nxt = update_plan_intake_state(
        base,
        updates={
            "primary_goal": "Target Time",
            "target_time": "3:40:00",
            "apply_coach_suggested_goal": True,
        },
    )
    assert nxt["draft"]["target_time"] == "3:40:00"
    assert nxt["draft"]["race_distance"] == "Marathon"
    assert nxt["ux"].get("intake_confirmed") is True
    assert nxt["ux"].get("runner_review_delivered") is True
    assert nxt["ux"].get("runner_tradeoff_resolved") is True
    assert nxt["ux"].get("plan_generation_confirmed") is not True


def test_confirmation_summary_readable_multiline_includes_target_time():
    state = update_plan_intake_state(
        None,
        updates={
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:40:00",
            "training_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            "long_run_day": "Sat",
        },
    )
    summary = state["confirmation_summary"]
    assert summary == (
        "- Marathon date: 10/11/2026\n"
        "- Target time: 3:40:00\n"
        "- Training days: Mon, Tue, Wed, Thu, Fri, Sat\n"
        "- Long runs on: Sat"
    )
    message = format_plan_intake_confirmation_message(summary)
    assert message.startswith("Here's what I have:\n\n")
    assert message.endswith("Does this look right?")
    assert ";" not in message
    assert "- Target time: 3:40:00" in message


def test_deterministic_confirmation_keeps_multiline_layout():
    """Prose guardrails collapse newlines — deterministic intake copy must not pass through them."""
    state = update_plan_intake_state(
        None,
        updates={
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:40:00",
            "training_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            "long_run_day": "Sat",
        },
    )
    from src.smartcoach_mobile_coach.orchestrator.plan_creation_branch import (
        _enforce_plan_creation_response_guardrails,
        _natural_plan_intake_fallback_question,
    )

    raw = _natural_plan_intake_fallback_question(state)
    assert "\n- Target time: 3:40:00\n" in raw
    assert raw.startswith("Here's what I have:\n\n")
    mangled = _enforce_plan_creation_response_guardrails(raw, plan_intake_state=state)
    assert mangled != raw
