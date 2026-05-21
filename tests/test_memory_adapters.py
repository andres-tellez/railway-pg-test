"""Contract-style tests for memory adapters."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from src.db.models.user_identity import UserIdentity
from src.smartcoach_mobile_coach.memory.adapters.durable_pg import DurableRepoPG
from src.smartcoach_mobile_coach.memory.adapters.interaction_pg import InteractionRepoPG
from src.smartcoach_mobile_coach.memory.adapters.state_pg import StateRepoPG
from src.smartcoach_mobile_coach.memory.adapters.summary_pg import SummaryRepoPG
from src.smartcoach_mobile_coach.memory.adapters.threads_pg import ThreadRepoPG
from src.smartcoach_mobile_coach.memory.domain.types import (
    DurableItem,
    InteractionRecord,
    OpenThread,
    Provenance,
    SessionSummaryItem,
    StateObservation,
)
from src.smartcoach_mobile_coach.memory.domain.vocab import (
    DurableType,
    InteractionFlag,
    Source,
    StateTag,
    ThreadTopic,
)


def _uid(test_db_session):
    uid = uuid.uuid4()
    test_db_session.add(UserIdentity(user_id=uid, name="Memory Adapter User"))
    test_db_session.flush()
    return uid


def test_durable_repo_roundtrip(test_db_session):
    uid = _uid(test_db_session)
    repo = DurableRepoPG(test_db_session)
    item = DurableItem(
        id=uuid.uuid4(),
        user_id=uid,
        text="I prefer Saturday long runs.",
        durable_type=DurableType.LONG_RUN_DAY,
        provenance=Provenance(
            source=Source.COACH_TOOL,
            captured_at=datetime.now(timezone.utc),
            conversation_id=None,
        ),
    )
    saved = repo.append(item)
    rows = repo.list_for_user(uid)
    assert saved.id in {r.id for r in rows}
    assert any(r.durable_type == DurableType.LONG_RUN_DAY for r in rows)


def test_summary_repo_roundtrip(test_db_session):
    uid = _uid(test_db_session)
    repo = SummaryRepoPG(test_db_session)
    item = SessionSummaryItem(
        id=uuid.uuid4(),
        user_id=uid,
        conversation_id=None,
        text="User discussed pacing confidence and race anxiety.",
        tags=("pacing", "confidence"),
        created_at=datetime.now(timezone.utc),
    )
    repo.append(item)
    out = repo.read_latest(uid)
    assert out is not None
    assert "pacing" in out.text.lower()
    assert "confidence" in out.tags


def test_interaction_repo_idempotent_record(test_db_session):
    uid = _uid(test_db_session)
    conv = uuid.uuid4()
    repo = InteractionRepoPG(test_db_session)
    base = InteractionRecord(
        id=uuid.uuid4(),
        user_id=uid,
        conversation_id=conv,
        flag=InteractionFlag.RECAPPED_RUN,
        key="12345",
        captured_at=datetime.now(timezone.utc),
    )
    a = repo.record(base)
    b = repo.record(base)
    assert a.id == b.id
    items = repo.list_recent(
        user_id=uid,
        conversation_id=conv,
        since=datetime.now(timezone.utc) - timedelta(days=1),
    )
    assert len(items) == 1


def test_state_repo_only_active(test_db_session):
    uid = _uid(test_db_session)
    repo = StateRepoPG(test_db_session)
    now = datetime.now(timezone.utc)
    active = StateObservation(
        id=uuid.uuid4(),
        user_id=uid,
        text="Mild headache after run.",
        tag=StateTag.HEADACHE,
        captured_at=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=6),
        provenance=Provenance(
            source=Source.USER_STATEMENT,
            captured_at=now - timedelta(hours=1),
            conversation_id=None,
            confidence=0.9,
        ),
    )
    expired = StateObservation(
        id=uuid.uuid4(),
        user_id=uid,
        text="Old fatigue note.",
        tag=StateTag.LOW_MOTIVATION,
        captured_at=now - timedelta(days=2),
        valid_until=now - timedelta(hours=1),
        provenance=Provenance(
            source=Source.USER_STATEMENT,
            captured_at=now - timedelta(days=2),
            conversation_id=None,
            confidence=0.8,
        ),
    )
    repo.append(active)
    repo.append(expired)
    items = repo.list_active(uid, now)
    assert len(items) == 1
    assert items[0].tag == StateTag.HEADACHE


def test_thread_repo_due_only(test_db_session):
    uid = _uid(test_db_session)
    repo = ThreadRepoPG(test_db_session)
    now = datetime.now(timezone.utc)
    due = OpenThread(
        id=uuid.uuid4(),
        user_id=uid,
        text="Follow up on calf soreness.",
        topic=ThreadTopic.INJURY_RECHECK,
        due_at=now - timedelta(minutes=1),
        status="open",
        created_at=now - timedelta(hours=2),
        provenance=Provenance(
            source=Source.SYSTEM,
            captured_at=now - timedelta(hours=2),
            conversation_id=None,
        ),
    )
    later = OpenThread(
        id=uuid.uuid4(),
        user_id=uid,
        text="Revisit long-run fueling next week.",
        topic=ThreadTopic.PROGRESS_CHECKIN,
        due_at=now + timedelta(days=2),
        status="open",
        created_at=now - timedelta(hours=1),
        provenance=Provenance(
            source=Source.SYSTEM,
            captured_at=now - timedelta(hours=1),
            conversation_id=None,
        ),
    )
    repo.append(due)
    repo.append(later)
    due_items = repo.list_due(uid, now)
    assert len(due_items) == 1
    assert due_items[0].topic == ThreadTopic.INJURY_RECHECK
