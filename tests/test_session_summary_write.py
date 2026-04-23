"""Phase F — session summary writer."""

from __future__ import annotations

import json
import uuid

import pytest

from src.db.models.user_identity import UserIdentity
from src.db.models.user_plan_memories import UserPlanMemory
from src.services.coach.session_summary_write import (
    collect_tool_names_from_agent_meta,
    extract_assistant_plain_text,
    filter_plan_memory_extractions,
    maybe_write_session_summary_after_turn,
    worth_persisting_extracted_plan_memory,
)
from src.services.security.external_apis.openai_service import OpenAIResponse


@pytest.fixture
def uid(test_db_session) -> uuid.UUID:
    u = uuid.uuid4()
    test_db_session.add(UserIdentity(user_id=u, name="S"))
    test_db_session.commit()
    return u


def test_collect_tool_names_order(monkeypatch):
    meta = {
        "timings_ms": {
            "agent_loop_rounds": [
                {"tools": [{"name": "get_weekly_plan"}, {"name": "get_user_context"}]},
                {"tools": [{"name": "get_weekly_plan"}]},
            ]
        }
    }
    assert collect_tool_names_from_agent_meta(meta) == [
        "get_weekly_plan",
        "get_user_context",
    ]


def test_worth_persisting_rejects_trivial_chaff():
    assert not worth_persisting_extracted_plan_memory(
        "Thanks that was a good run today"
    )
    assert not worth_persisting_extracted_plan_memory(
        "abcdefghijklmnopqrstuvwxyz1234567890abcd"
    )
    assert worth_persisting_extracted_plan_memory(
        "I prefer Saturday mornings for my long runs because of my work travel schedule"
    )


def test_filter_plan_memory_extractions_drops_noise():
    raw = [
        "Thanks, awesome run today with friends",
        "I prefer Saturday mornings for my long runs because of my work schedule",
    ]
    assert filter_plan_memory_extractions(raw) == [raw[1]]


def test_extract_assistant_plain_text_dict():
    assert (
        extract_assistant_plain_text({"type": "text", "content": " Hello ", "data": {}})
        == "Hello"
    )


def test_maybe_write_skipped_when_disabled(test_db_session, uid, monkeypatch):
    monkeypatch.delenv("SMARTCOACH_SESSION_SUMMARY_WRITER_ENABLED", raising=False)
    maybe_write_session_summary_after_turn(
        test_db_session,
        internal_user_id=str(uid),
        conversation_id=uuid.uuid4(),
        user_message="hi",
        assistant_reply="bye",
        meta={},
    )
    test_db_session.commit()
    from src.db.models.session_summaries import SessionSummary

    assert test_db_session.query(SessionSummary).count() == 0


def test_maybe_write_persists_when_enabled(test_db_session, uid, monkeypatch):
    monkeypatch.setenv("SMARTCOACH_SESSION_SUMMARY_WRITER_ENABLED", "1")

    class _FakeSvc:
        def chat_completion(self, **kwargs):
            payload = {
                "summary_text": "User asked about weekly volume.",
                "thread_tags": ["weekly_volume"],
                "plan_memories": [],
            }
            return OpenAIResponse(
                content=json.dumps(payload),
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
                cost=0.0,
                model="gpt-4o-mini",
            )

    monkeypatch.setattr(
        "src.services.coach.session_summary_write.get_openai_service",
        lambda: _FakeSvc(),
    )

    cid = uuid.uuid4()
    maybe_write_session_summary_after_turn(
        test_db_session,
        internal_user_id=str(uid),
        conversation_id=cid,
        user_message="How is my week?",
        assistant_reply="Looking solid.",
        meta={
            "timings_ms": {
                "agent_loop_rounds": [{"tools": [{"name": "get_weekly_plan"}]}]
            }
        },
    )
    test_db_session.commit()

    from src.db.models.session_summaries import SessionSummary

    rows = test_db_session.query(SessionSummary).filter_by(user_id=uid).all()
    assert len(rows) == 1
    assert "weekly volume" in rows[0].summary_text.lower()
    assert rows[0].thread_tags == ["weekly_volume"]


def test_maybe_write_filters_trivial_plan_memories(test_db_session, uid, monkeypatch):
    monkeypatch.setenv("SMARTCOACH_SESSION_SUMMARY_WRITER_ENABLED", "1")

    class _FakeSvc:
        def chat_completion(self, **kwargs):
            payload = {
                "summary_text": "Discussed scheduling and preferences.",
                "thread_tags": ["scheduling"],
                "plan_memories": [
                    "Thanks that was a good run today",
                    "I prefer Saturday mornings for my long runs because of my work schedule",
                ],
            }
            return OpenAIResponse(
                content=json.dumps(payload),
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
                cost=0.0,
                model="gpt-4o-mini",
            )

    monkeypatch.setattr(
        "src.services.coach.session_summary_write.get_openai_service",
        lambda: _FakeSvc(),
    )

    maybe_write_session_summary_after_turn(
        test_db_session,
        internal_user_id=str(uid),
        conversation_id=uuid.uuid4(),
        user_message="When should I long run?",
        assistant_reply="We can shift volume slightly.",
        meta={},
    )
    test_db_session.commit()

    mems = test_db_session.query(UserPlanMemory).filter_by(user_id=uid).all()
    assert len(mems) == 1
    assert "Saturday" in mems[0].memory_text
