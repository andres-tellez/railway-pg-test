"""Smoke: replay harness hits real DB-backed build_runner_evidence + readiness."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from src.db.models.activities import Activity
from src.services.training_plan.data_collection_service import DataCollectionService


def _load_replay_module():
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "replay_readiness_decision.py"
    spec = importlib.util.spec_from_file_location("replay_readiness_decision", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_replay_readiness_decision_smoke(
    test_db_session, seed_test_data, monkeypatch
) -> None:
    _orig_fetch = DataCollectionService.fetch_strava_activities

    # Under SQLite test DBs, source="auto" can bypass rows the ORM has written to
    # strava_activities; force "table" so build_runner_evidence matches seeded rows.
    def _fetch_table_only(*args, **kwargs):
        kwargs["source"] = "table"
        return _orig_fetch(*args, **kwargs)

    monkeypatch.setattr(
        DataCollectionService,
        "fetch_strava_activities",
        _fetch_table_only,
    )
    monkeypatch.setattr(
        "src.coaching_intelligence.pre_generation_runner_assessment._coach_memory_stats",
        lambda *_a, **_k: None,
    )

    uid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    anchor = date.today()
    run_d = anchor - timedelta(days=5)
    run_dt = datetime(run_d.year, run_d.month, run_d.day, 10, 0, 0)
    for row in test_db_session.query(Activity).all():
        row.user_id = uid
        row.start_date = run_dt
        row.type = "Run"
        row.conv_distance = 3.1
    test_db_session.flush()
    assert test_db_session.query(Activity).count() >= 1
    acts_for_user = (
        test_db_session.query(Activity).filter(Activity.user_id == uid).all()
    )
    assert len(acts_for_user) >= 1, [
        (a.activity_id, a.user_id, a.type, a.start_date)
        for a in test_db_session.query(Activity).all()
    ]
    fetched = DataCollectionService.fetch_strava_activities(
        test_db_session, str(uid), weeks=12, source="table"
    )
    assert len(fetched) >= 1, f"expected strava fetch rows, got {fetched!r}"

    mod = _load_replay_module()
    out = mod.run_replay(
        session=test_db_session,
        user_id=str(uid),
        anchor_local_date=date(2026, 5, 12),
        plan_intake_state=mod.default_replay_plan_intake_state(),
        alignment_enabled=False,
        trace_id="smoke-replay-trace",
    )

    ev = out.get("runner_evidence")
    assert isinstance(ev, dict)
    assert int(ev.get("activities_found") or 0) >= 1
    assert out.get("goal_profile")
    verdict = out.get("readiness_verdict")
    assert isinstance(verdict, dict)
    assert verdict.get("trace_id") == "smoke-replay-trace"
    assert verdict.get("runner_analysis_display")
