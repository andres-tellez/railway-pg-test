"""Card-once run-summary layout override tests."""

from __future__ import annotations

import uuid

from src.smartcoach_mobile_coach.routes import _apply_card_once_layout_override


class _MemoryServiceStub:
    def __init__(self, has_marker: bool) -> None:
        self._has_marker = has_marker

    def has_interaction(self, **kwargs) -> bool:
        return self._has_marker


def _payload_lab_shaped_wire_id(activity_id: int) -> dict:
    """Shape produced when ``facts`` omits nested activity_id (Run Review Lab)."""
    return {
        "type": "run_summary",
        "content": "x",
        "data": {
            "activity_id": activity_id,
            "facts": {"title": "Run", "local_date": "2026-05-21"},
        },
    }


def _payload(activity_id: int) -> dict:
    return {
        "type": "run_summary",
        "content": "x",
        "data": {"facts": {"activity_id": activity_id}},
    }


def test_card_once_forces_inline_when_marker_exists(monkeypatch):
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.memory.build_memory_service",
        lambda session, cfg: _MemoryServiceStub(has_marker=True),
    )
    payload, should_mark, activity_id = _apply_card_once_layout_override(
        session=object(),
        user_id=str(uuid.uuid4()),
        conversation_id=uuid.uuid4(),
        payload=_payload(123),
    )
    assert should_mark is False
    assert activity_id == 123
    assert payload.get("run_summary_layout") == "inline"


def test_card_once_marks_when_activity_id_only_on_data(monkeypatch):
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.memory.build_memory_service",
        lambda session, cfg: _MemoryServiceStub(has_marker=False),
    )
    payload, should_mark, activity_id = _apply_card_once_layout_override(
        session=object(),
        user_id=str(uuid.uuid4()),
        conversation_id=uuid.uuid4(),
        payload=_payload_lab_shaped_wire_id(909),
    )
    assert should_mark is True
    assert activity_id == 909


def test_card_once_marks_first_recap_when_no_marker(monkeypatch):
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.memory.build_memory_service",
        lambda session, cfg: _MemoryServiceStub(has_marker=False),
    )
    payload, should_mark, activity_id = _apply_card_once_layout_override(
        session=object(),
        user_id=str(uuid.uuid4()),
        conversation_id=uuid.uuid4(),
        payload=_payload(456),
    )
    assert should_mark is True
    assert activity_id == 456
    assert "run_summary_layout" not in payload
