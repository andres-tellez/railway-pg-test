"""Evidence Pack MVP tests (easy/Z2 only)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List

import src.smartcoach_mobile_coach.run_review.evidence_pack as ep_mod
from src.smartcoach_mobile_coach.run_review.context_builder import stub_context_for_test
from src.smartcoach_mobile_coach.run_review.prompt import (
    build_run_review_system_appendix,
)


def _act(
    *,
    aid: int,
    days_ago: int,
    distance_m: float,
    moving_s: int,
    avg_hr: float,
    max_hr: float,
    executed_type: str,
    planned_type: str,
) -> Any:
    now = datetime(2026, 5, 16, 12, 0, 0)
    return SimpleNamespace(
        activity_id=aid,
        athlete_id=7,
        type="Run",
        start_date=now - timedelta(days=days_ago),
        distance=distance_m,
        moving_time=moving_s,
        average_heartrate=avg_hr,
        max_heartrate=max_hr,
        total_elevation_gain=110.0,
        executed_type=executed_type,
        planned_type=planned_type,
        hr_zone_1=300.0,
        hr_zone_2=1200.0,
        hr_zone_3=300.0,
        hr_zone_4=0.0,
        hr_zone_5=0.0,
    )


class _FakeQuery:
    def __init__(self, *, current: Any, candidates: List[Any]):
        self.current = current
        self.candidates = candidates

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def one_or_none(self):
        return self.current

    def all(self):
        return self.candidates


class _FakeSession:
    def __init__(self, *, current: Any, candidates: List[Any]):
        self.current = current
        self.candidates = candidates

    def query(self, *_args, **_kwargs):
        return _FakeQuery(current=self.current, candidates=self.candidates)


def _contains_forbidden_keys(obj: Any, forbidden: set[str]) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in forbidden:
                return True
            if _contains_forbidden_keys(v, forbidden):
                return True
        return False
    if isinstance(obj, list):
        return any(_contains_forbidden_keys(v, forbidden) for v in obj)
    return False


def test_build_evidence_pack_easy_turn_includes_similar_runs_and_deltas(
    monkeypatch,
) -> None:
    current = _act(
        aid=9001,
        days_ago=0,
        distance_m=8046.72,  # ~5mi
        moving_s=2847,
        avg_hr=132.0,
        max_hr=143.0,
        executed_type="easy",
        planned_type="easy",
    )
    candidates = [
        _act(
            aid=8000 + i,
            days_ago=i + 1,
            distance_m=8000 + (i * 50),
            moving_s=2900 + (i * 10),
            avg_hr=130.0 + i,
            max_hr=141.0 + i,
            executed_type="easy",
            planned_type="easy",
        )
        for i in range(7)
    ]
    session = _FakeSession(current=current, candidates=candidates)

    monkeypatch.setattr(ep_mod, "get_primary_athlete_id", lambda *_a, **_kw: 7)
    monkeypatch.setattr(
        ep_mod,
        "build_user_context_payload",
        lambda *_a, **_kw: {
            "race_goal": {"race_name": "Half Marathon", "goal_time": "1:45:00"},
            "plan": {"current_phase": "Base", "current_week_number": 3},
        },
    )
    monkeypatch.setattr(
        ep_mod,
        "compute_recent_run_rollup_for_user",
        lambda *_a, **_kw: {
            "runs_28d": 11,
            "weeks_with_runs_28d": 4,
            "longest_run_meters_28d": 19312.0,
        },
    )
    monkeypatch.setattr(
        ep_mod,
        "get_training_progress",
        lambda *_a, **_kw: {
            "weekly_summaries": [
                {"total_miles": 18.2},
                {"total_miles": 22.1},
                {"total_miles": 20.0},
                {"total_miles": 24.8},
            ]
        },
    )

    facts: Dict[str, Any] = {
        "distance_display": "5.01 mi",
        "moving_time_display": "47:27",
        "avg_pace_display": "9:29/mi",
        "avg_heart_rate_display": "132 bpm",
        "max_heart_rate_display": "143 bpm",
        "execution_summary": {
            "plan_status": "executed",
            "planned": {"type": "easy", "miles": 5.0},
            "violated_rest_day": False,
        },
    }
    pack, trace = ep_mod.build_evidence_pack(
        session=session,
        internal_user_id="7cd7fa90-84b9-4928-b26c-09474fd71078",
        activity_id=9001,
        anchor_local_date="2026-05-16",
        facts=facts,
        workout_intent=SimpleNamespace(planned_type="easy"),
        is_easy_run=True,
    )
    assert pack is not None
    assert trace["present"] is True
    assert pack["current_run"]["distance"] == "5.01 mi"
    assert pack["current_run"]["avg_pace"] == "9:29/mi"
    assert pack["current_run"]["avg_hr"] == "132 bpm"
    assert pack["current_run"]["max_hr"] == "143 bpm"
    assert pack["similar_runs"]["selection_basis"] in {
        "executed_type",
        "planned_type",
        "distance_band",
    }
    assert len(pack["similar_runs"]["rows"]) <= 5
    assert pack["similar_deltas"]["cohort"]["count"] == len(
        pack["similar_runs"]["rows"]
    )
    assert "pace_delta_sec_per_mi" in pack["similar_deltas"]["today_vs_cohort"]
    assert "hr_delta_bpm" in pack["similar_deltas"]["today_vs_cohort"]
    assert trace["size_chars"] <= ep_mod.EVIDENCE_PACK_MAX_CHARS


def test_build_evidence_pack_skips_non_easy_turn() -> None:
    pack, trace = ep_mod.build_evidence_pack(
        session=_FakeSession(current=None, candidates=[]),
        internal_user_id="7cd7fa90-84b9-4928-b26c-09474fd71078",
        activity_id=1,
        anchor_local_date="2026-05-16",
        facts={},
        workout_intent=SimpleNamespace(planned_type="tempo"),
        is_easy_run=False,
    )
    assert pack is None
    assert trace["present"] is False
    assert trace["reason"] == "non_easy_turn"


def test_evidence_pack_prompt_block_and_forbidden_keys() -> None:
    evidence_pack = {
        "version": "run_review_evidence_pack_v1_easy",
        "current_run": {"distance": "5.01 mi", "avg_pace": "9:29/mi"},
        "similar_runs": {"selection_basis": "executed_type", "rows": []},
        "similar_deltas": {"cohort": {"count": 0}, "today_vs_cohort": {}},
    }
    forbidden = {
        "interpretation_signal",
        "coach_meaning",
        "aerobic_efficiency_improved",
        "faster_at_lower_hr",
        "good_run",
        "bad_run",
    }
    assert _contains_forbidden_keys(evidence_pack, forbidden) is False

    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-16",
        facts={"execution_summary": {"planned": {"type": "easy"}}},
        evidence_pack=evidence_pack,
        scope="single_run",
        is_easy_run=True,
    )
    appendix = build_run_review_system_appendix(ctx)
    assert "## Evidence Pack (factual only)" in appendix
    assert "Use this pack as structured evidence." in appendix
    assert "Use the evidence to find the story of the run" in appendix
    assert "Do not summarize the RunSummary card" in appendix
    assert "If ``similar_runs_count`` is small" in appendix
    assert "Example shape (illustrative only, not a script)" not in appendix
    assert "This looked like a clean easy run overall." not in appendix


def test_long_run_with_evidence_pack_allows_4_to_8_sentences() -> None:
    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-16",
        facts={"execution_summary": {"planned": {"type": "long"}}},
        evidence_pack={"version": "run_review_evidence_pack_v1_easy"},
        scope="single_run",
        is_easy_run=True,
    )
    appendix = build_run_review_system_appendix(ctx)
    assert (
        "Keep it concise: **4–8 sentences** are allowed for this long easy/Z2 run"
        in appendix
    )
