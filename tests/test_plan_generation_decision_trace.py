from __future__ import annotations

import copy
import uuid

from src.db.models.user_identity import UserIdentity
from src.routes.plan_generation_v2 import (
    build_standard_draft_payload,
    run_v2_plan_generation,
)
from src.services.coach.user_plan_memory_service import (
    MEMORY_SOURCE_COACH_TOOL,
    append_plan_memory,
    coach_memory_entries_for_plan_generation,
    coach_memory_hints_for_plan_generation,
)
from src.services.training_plan.decision_trace import (
    resolve_long_run_day,
    resolve_training_days,
)


def _assert_trace_integrity(reason) -> None:
    if reason.source == "memory":
        assert reason.memory_ids
    else:
        assert reason.memory_ids == []


def test_resolve_training_days_prefers_explicit_user_input():
    value, reason = resolve_training_days(
        plan_request={"training_days": ["Tue", "Thu", "Sat"]},
        hints=["Mon, Wed, Fri"],
        memories=[
            {
                "id": "memory-1",
                "text": "Mon, Wed, Fri",
                "memory_type": "training_days",
            }
        ],
        requested_training_days=["Tue", "Thu", "Sat"],
    )

    assert value == ["Tue", "Thu", "Sat"]
    assert reason.source == "user_input"
    assert reason.rationale == "user provided"
    _assert_trace_integrity(reason)


def test_resolve_training_days_from_memory_includes_memory_ids():
    value, reason = resolve_training_days(
        plan_request={},
        hints=[],
        memories=[
            {
                "id": "memory-1",
                "text": "Tue, Thu, Sun",
                "memory_type": "training_days",
            }
        ],
        requested_training_days=None,
    )

    assert value == ["Tue", "Thu", "Sun"]
    assert reason.source == "memory"
    assert reason.memory_ids == ["memory-1"]
    assert reason.rationale == "derived from user memory"
    _assert_trace_integrity(reason)


def test_resolve_training_days_defaults_without_memory():
    value, reason = resolve_training_days(
        plan_request={},
        hints=[],
        memories=[],
        requested_training_days=None,
    )

    assert value == ["Mon", "Wed", "Thu", "Sat"]
    assert reason.source == "default_fallback"
    assert reason.rationale == "default selection (Mon, Wed, Thu, Sat)"
    _assert_trace_integrity(reason)


def test_resolve_training_days_falls_back_when_memory_not_usable():
    value, reason = resolve_training_days(
        plan_request={},
        hints=["I can only run 4 days per week"],
        memories=[
            {
                "id": "memory-1",
                "text": "I can only run 4 days per week",
                "memory_type": "training_days",
            }
        ],
        requested_training_days=None,
    )

    assert value == ["Mon", "Wed", "Thu", "Sat"]
    assert reason.source == "default_fallback"
    assert reason.rationale == "memory not actionable for weekdays, using fallback"
    _assert_trace_integrity(reason)


def test_resolve_training_days_memory_ids_are_sorted_and_unique():
    value, reason = resolve_training_days(
        plan_request={},
        hints=[],
        memories=[
            {
                "id": "memory-b",
                "text": "Tue, Thu, Sun",
                "memory_type": "training_days",
            },
            {
                "id": "memory-a",
                "text": "Tue, Thu, Sun",
                "memory_type": "training_days",
            },
            {
                "id": "memory-b",
                "text": "Tue, Thu, Sun",
                "memory_type": "training_days",
            },
            {
                "id": "longrun-1",
                "text": "Keep long runs on Sunday",
                "memory_type": "long_run_day",
            },
        ],
        requested_training_days=None,
    )

    assert value == ["Tue", "Thu", "Sun"]
    assert reason.source == "memory"
    assert reason.memory_ids == ["memory-a", "memory-b"]
    _assert_trace_integrity(reason)


def test_resolve_long_run_day_prefers_explicit_user_input():
    value, reason = resolve_long_run_day(
        plan_request={"long_run_day": "Sun"},
        hints=["Keep long runs on Saturday"],
        memories=[
            {
                "id": "memory-1",
                "text": "Keep long runs on Saturday",
                "memory_type": "long_run_day",
            }
        ],
        training_days=["Tue", "Thu", "Sat", "Sun"],
    )

    assert value == "Sun"
    assert reason.source == "user_input"
    assert reason.rationale == "user provided"
    _assert_trace_integrity(reason)


def test_resolve_long_run_day_from_memory_includes_memory_ids():
    value, reason = resolve_long_run_day(
        plan_request={},
        hints=["Keep long runs on Saturday"],
        memories=[
            {
                "id": "memory-1",
                "text": "Keep long runs on Saturday",
                "memory_type": "long_run_day",
            }
        ],
        training_days=["Tue", "Thu", "Sat", "Sun"],
    )

    assert value == "Sat"
    assert reason.source == "memory"
    assert reason.memory_ids == ["memory-1"]
    assert reason.rationale == "derived from user memory"
    _assert_trace_integrity(reason)


def test_resolve_long_run_day_defaults_without_memory():
    value, reason = resolve_long_run_day(
        plan_request={},
        hints=[],
        memories=[],
        training_days=["Tue", "Thu", "Sat", "Sun"],
    )

    assert value == "Sat"
    assert reason.source == "default_fallback"
    assert reason.rationale == "default selection (Sat > Sun > last)"
    _assert_trace_integrity(reason)


def test_resolve_long_run_day_ignores_memory_when_day_not_in_training_days():
    value, reason = resolve_long_run_day(
        plan_request={},
        hints=["Keep long runs on Saturday"],
        memories=[
            {
                "id": "memory-1",
                "text": "Keep long runs on Saturday",
                "memory_type": "long_run_day",
            }
        ],
        training_days=["Tue", "Thu", "Sun"],
    )

    assert value == "Sun"
    assert reason.source == "default_fallback"
    assert reason.rationale == "memory value not in training_days, using fallback"
    _assert_trace_integrity(reason)


def test_training_days_memory_can_force_long_run_day_memory_to_fallback():
    training_days, training_reason = resolve_training_days(
        plan_request={},
        hints=[],
        memories=[
            {
                "id": "training-memory",
                "text": "Tue, Thu, Sun",
                "memory_type": "training_days",
            },
            {
                "id": "longrun-memory",
                "text": "Keep long runs on Saturday",
                "memory_type": "long_run_day",
            },
        ],
        requested_training_days=None,
    )
    long_run_day, long_run_reason = resolve_long_run_day(
        plan_request={},
        hints=["Keep long runs on Saturday"],
        memories=[
            {
                "id": "training-memory",
                "text": "Tue, Thu, Sun",
                "memory_type": "training_days",
            },
            {
                "id": "longrun-memory",
                "text": "Keep long runs on Saturday",
                "memory_type": "long_run_day",
            },
        ],
        training_days=training_days,
    )

    assert training_days == ["Tue", "Thu", "Sun"]
    assert training_reason.source == "memory"
    assert long_run_day == "Sun"
    assert long_run_reason.source == "default_fallback"
    assert long_run_reason.memory_ids == []
    assert (
        long_run_reason.rationale == "memory value not in training_days, using fallback"
    )


def test_run_v2_plan_generation_memory_mode_changes_long_run_day(
    test_db_session, monkeypatch
):
    user_id = uuid.uuid4()
    test_db_session.add(UserIdentity(user_id=user_id, name="Runner"))
    test_db_session.flush()
    row, dup = append_plan_memory(
        test_db_session,
        user_id,
        "Keep long runs on Sunday",
        source=MEMORY_SOURCE_COACH_TOOL,
    )
    assert row is not None
    assert not dup
    test_db_session.commit()
    assert coach_memory_hints_for_plan_generation(test_db_session, user_id) == [
        "Keep long runs on Sunday"
    ]
    assert (
        coach_memory_entries_for_plan_generation(test_db_session, user_id)[0][
            "memory_type"
        ]
        == "long_run_day"
    )

    monkeypatch.setattr(
        "src.routes.plan_generation_v2.get_user_profile",
        lambda _session, _user_id: {"unit_system": "imperial"},
    )
    captured_requests = []

    def _fake_generate(self, runner_ctx, mode="prefill", week_logs=None):
        captured_requests.append(copy.deepcopy(runner_ctx["plan_request"]))
        long_run_day, reason = self._determine_long_run_day(
            runner_ctx["plan_request"], runner_ctx["training_days"]
        )
        return {
            "valid": True,
            "violations": [],
            "validated_plan": {"long_run_day": long_run_day},
            "draft": {"long_run_day": long_run_day},
            "decision_trace": [reason.to_dict()],
        }

    monkeypatch.setattr(
        "src.services.training_plan.v2.plan_generation_orchestrator_v2.PlanGenerationOrchestratorV2.generate_longrun_first",
        _fake_generate,
    )

    base_request = {
        "race_distance": "Marathon",
        "race_date": "2026-10-11",
        "primary_goal": "Just Finish",
        "training_days": ["Tue", "Thu", "Sat", "Sun"],
    }

    with_memory, _ = run_v2_plan_generation(
        session=test_db_session,
        user_id=str(user_id),
        plan_request=copy.deepcopy(base_request),
        memory_mode="on",
    )
    without_memory, _ = run_v2_plan_generation(
        session=test_db_session,
        user_id=str(user_id),
        plan_request=copy.deepcopy(base_request),
        memory_mode="off",
    )

    assert captured_requests[0]["coach_memory_hints"] == ["Keep long runs on Sunday"]
    assert (
        captured_requests[0]["coach_memory_memories"][0]["memory_type"]
        == "long_run_day"
    )
    assert "coach_memory_hints" not in captured_requests[1]
    assert with_memory["validated_plan"]["long_run_day"] == "Sun"
    assert without_memory["validated_plan"]["long_run_day"] == "Sat"
    assert (
        with_memory["validated_plan"]["long_run_day"]
        != without_memory["validated_plan"]["long_run_day"]
    )

    assert with_memory["decision_trace"][0]["field"] == "long_run_day"
    assert with_memory["decision_trace"][0]["source"] == "memory"
    assert with_memory["decision_trace"][0]["memory_ids"] == [str(row.id)]
    assert with_memory["decision_trace"][0]["rationale"] == "derived from user memory"
    assert without_memory["decision_trace"][0]["source"] == "default_fallback"
    assert (
        without_memory["decision_trace"][0]["rationale"]
        == "default selection (Sat > Sun > last)"
    )


def test_run_v2_plan_generation_memory_mode_changes_training_days(
    test_db_session, monkeypatch
):
    user_id = uuid.uuid4()
    test_db_session.add(UserIdentity(user_id=user_id, name="Runner"))
    test_db_session.flush()
    row, dup = append_plan_memory(
        test_db_session,
        user_id,
        "Tue, Thu, Sun",
        source=MEMORY_SOURCE_COACH_TOOL,
        memory_type="training_days",
    )
    assert row is not None
    assert not dup
    test_db_session.commit()

    monkeypatch.setattr(
        "src.routes.plan_generation_v2.get_user_profile",
        lambda _session, _user_id: {"unit_system": "imperial"},
    )

    def _fake_generate(self, runner_ctx, mode="prefill", week_logs=None):
        training_days, training_reason = self._determine_training_days(
            runner_ctx["plan_request"], runner_ctx["training_days"]
        )
        runner_ctx["plan_request"]["training_days"] = training_days
        long_run_day, long_run_reason = self._determine_long_run_day(
            runner_ctx["plan_request"], training_days
        )
        return {
            "valid": True,
            "violations": [],
            "validated_plan": {
                "training_days": training_days,
                "long_run_day": long_run_day,
            },
            "draft": {
                "training_days": training_days,
                "long_run_day": long_run_day,
            },
            "decision_trace": [
                training_reason.to_dict(),
                long_run_reason.to_dict(),
            ],
        }

    monkeypatch.setattr(
        "src.services.training_plan.v2.plan_generation_orchestrator_v2.PlanGenerationOrchestratorV2.generate_longrun_first",
        _fake_generate,
    )

    base_request = {
        "race_distance": "Marathon",
        "race_date": "2026-10-11",
        "primary_goal": "Just Finish",
    }

    with_memory, _ = run_v2_plan_generation(
        session=test_db_session,
        user_id=str(user_id),
        plan_request=copy.deepcopy(base_request),
        memory_mode="on",
    )
    without_memory, _ = run_v2_plan_generation(
        session=test_db_session,
        user_id=str(user_id),
        plan_request=copy.deepcopy(base_request),
        memory_mode="off",
    )

    assert with_memory["validated_plan"]["training_days"] == ["Tue", "Thu", "Sun"]
    assert without_memory["validated_plan"]["training_days"] == [
        "Mon",
        "Wed",
        "Thu",
        "Sat",
    ]
    assert with_memory["decision_trace"][0]["field"] == "training_days"
    assert with_memory["decision_trace"][0]["source"] == "memory"
    assert with_memory["decision_trace"][0]["memory_ids"] == [str(row.id)]
    assert with_memory["decision_trace"][0]["rationale"] == "derived from user memory"
    assert without_memory["decision_trace"][0]["field"] == "training_days"
    assert without_memory["decision_trace"][0]["source"] == "default_fallback"


def test_build_standard_draft_payload_surfaces_decision_trace():
    trace = [
        {
            "field": "long_run_day",
            "value": "Sun",
            "source": "memory",
            "memory_ids": ["memory-1"],
            "rationale": "derived from user memory",
        }
    ]
    payload = build_standard_draft_payload(
        validation_result={
            "valid": True,
            "violations": [],
            "validated_plan": {"long_run_day": "Sun"},
            "decision_trace": trace,
        }
    )

    assert payload["validation"]["decision_trace"] == trace
