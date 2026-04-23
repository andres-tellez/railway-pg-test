"""Phase F — user plan memory helpers."""

from __future__ import annotations

import uuid

import pytest

from src.db.models.user_identity import UserIdentity
from src.db.models.user_plan_memories import UserPlanMemory
from src.services.coach.user_plan_memory_service import (
    MEMORY_SOURCE_COACH_TOOL,
    append_plan_memory,
    coach_memory_hints_for_plan_generation,
    infer_long_run_day_from_memory_hints,
    infer_memory_type,
    memories_for_user_context,
    memory_text_similarity,
)


@pytest.fixture
def uid() -> uuid.UUID:
    return uuid.uuid4()


def test_infer_long_run_day_from_memory_hints(test_db_session, uid):
    test_db_session.add(UserIdentity(user_id=uid, name="T"))
    test_db_session.commit()
    hints = ["User wants long run on Saturday mornings"]
    assert infer_long_run_day_from_memory_hints(hints, ["Mon", "Wed", "Sat"]) == "Sat"


def test_infer_long_run_day_requires_long_run_phrase(test_db_session, uid):
    test_db_session.add(UserIdentity(user_id=uid, name="T"))
    test_db_session.commit()
    hints = ["User prefers Saturday for easy runs"]
    assert infer_long_run_day_from_memory_hints(hints, ["Mon", "Sat"]) is None


def test_append_and_list_roundtrip(test_db_session, uid):
    test_db_session.add(UserIdentity(user_id=uid, name="T"))
    test_db_session.flush()
    row, dup = append_plan_memory(
        test_db_session,
        uid,
        " Prefers Saturday long runs ",
        source=MEMORY_SOURCE_COACH_TOOL,
    )
    assert row is not None
    assert not dup
    assert row.memory_type == "long_run_day"
    test_db_session.commit()

    ctx = memories_for_user_context(test_db_session, uid)
    assert len(ctx) == 1
    assert ctx[0]["text"] == "Prefers Saturday long runs"
    assert ctx[0]["source"] == MEMORY_SOURCE_COACH_TOOL
    assert ctx[0]["memory_type"] == "long_run_day"

    hints = coach_memory_hints_for_plan_generation(test_db_session, uid)
    assert hints == ["Prefers Saturday long runs"]


def test_dedupe_similar_wording_no_extra_row(test_db_session, uid):
    test_db_session.add(UserIdentity(user_id=uid, name="T"))
    test_db_session.flush()
    a, d1 = append_plan_memory(
        test_db_session,
        uid,
        "Prefer Saturday for my long run",
        source=MEMORY_SOURCE_COACH_TOOL,
    )
    assert not d1
    test_db_session.commit()

    b, d2 = append_plan_memory(
        test_db_session,
        uid,
        "I prefer Saturday for my long run please",
        source=MEMORY_SOURCE_COACH_TOOL,
    )
    assert d2
    assert a is not None and b is not None
    assert a.id == b.id
    assert test_db_session.query(UserPlanMemory).filter_by(user_id=uid).count() == 1


def test_memory_type_inference_examples():
    assert (
        infer_memory_type("I can only run 4 days per week for training")
        == "training_days"
    )
    assert (
        infer_memory_type("Doctor said I must avoid doubles because of ankle injury")
        == "constraint"
    )
    assert (
        infer_memory_type("My goal is to qualify for Boston at this marathon") == "goal"
    )
    assert infer_memory_type("I would rather do easy miles on Monday") == "preference"


def test_max_twenty_evicts_oldest(test_db_session, uid):
    test_db_session.add(UserIdentity(user_id=uid, name="T"))
    test_db_session.flush()
    first_key = str(uuid.uuid4())
    _, _ = append_plan_memory(
        test_db_session,
        uid,
        f"I must avoid speedwork after knee injury until doctor clears {first_key} for marathon training",
        source=MEMORY_SOURCE_COACH_TOOL,
    )
    for _ in range(19):
        frag = str(uuid.uuid4())
        t, _ = append_plan_memory(
            test_db_session,
            uid,
            f"I must avoid hills after ankle injury until physio clears {frag} for marathon training",
            source=MEMORY_SOURCE_COACH_TOOL,
        )
        assert t is not None
    test_db_session.commit()
    assert test_db_session.query(UserPlanMemory).filter_by(user_id=uid).count() == 20

    newest = (
        "I must avoid icy trails after knee injury until coach clears "
        f"{uuid.uuid4()} for marathon training plan"
    )
    row, dup = append_plan_memory(
        test_db_session, uid, newest, source=MEMORY_SOURCE_COACH_TOOL
    )
    assert row is not None
    assert not dup
    test_db_session.commit()
    rows = (
        test_db_session.query(UserPlanMemory)
        .filter_by(user_id=uid)
        .order_by(UserPlanMemory.created_at.asc())
        .all()
    )
    assert len(rows) == 20
    assert (
        test_db_session.query(UserPlanMemory)
        .filter(UserPlanMemory.memory_text.like(f"%{first_key}%"))
        .count()
        == 0
    )
    assert any(newest[:40] in r.memory_text for r in rows)


def test_context_prioritizes_constraint_over_preference(test_db_session, uid):
    test_db_session.add(UserIdentity(user_id=uid, name="T"))
    test_db_session.flush()
    append_plan_memory(
        test_db_session,
        uid,
        "I would rather keep all my easy runs on Wednesday afternoons",
        source=MEMORY_SOURCE_COACH_TOOL,
    )
    test_db_session.commit()
    append_plan_memory(
        test_db_session,
        uid,
        "Doctor said I must avoid any hard intervals until my knee injury heals",
        source=MEMORY_SOURCE_COACH_TOOL,
    )
    test_db_session.commit()

    ctx = memories_for_user_context(test_db_session, uid)
    assert len(ctx) == 2
    assert "knee" in ctx[0]["text"].lower() or "injury" in ctx[0]["text"].lower()
    assert ctx[0]["memory_type"] == "constraint"


def test_similarity_threshold_boundary():
    a = "Prefer Saturday for my long run in marathon training plan schedule"
    b = "I prefer Saturday for my long run in marathon training plan schedule"
    assert memory_text_similarity(a, b) >= 0.85
