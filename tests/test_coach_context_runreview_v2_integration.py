"""Integration-style test: RunReview V2 receives CoachSnapshot appendix when enabled."""

from __future__ import annotations

from src.smartcoach_mobile_coach.coach_context.schemas import (
    CoachSnapshot,
    SnapshotBuildResult,
)
from src.smartcoach_mobile_coach.run_review.classifier import ClassifierResult
from src.smartcoach_mobile_coach.run_review.config import RunReviewConfig
from src.smartcoach_mobile_coach.run_review.context import (
    RunReviewContext,
    WorkoutIntent,
)
from src.smartcoach_mobile_coach.run_review.responder import ResponderOutput
import src.smartcoach_mobile_coach.run_review.entry as entry_mod


def _cfg(enabled: bool = True) -> RunReviewConfig:
    return RunReviewConfig(
        enabled=enabled,
        classifier_mode="heuristic",
        fetch_splits=False,
        include_comparisons=False,
        max_response_tokens=500,
        classifier_max_tokens=200,
        classifier_timeout_s=6.0,
        responder_timeout_s=10.0,
        responder_model_override="",
        classifier_model="gpt-4o-mini",
    )


def _ctx() -> RunReviewContext:
    return RunReviewContext(
        activity_id=10,
        anchor_local_date="2026-05-15",
        facts={"execution_summary": {"planned": {"type": "easy"}}},
        workout_intent=WorkoutIntent(planned_type="easy", plan_status="executed"),
        resolved_via="find_runs_by_date",
        scope="single_run",
    )


def test_runreview_v2_includes_snapshot_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("SMARTCOACH_COACH_CONTEXT_V1", "true")
    monkeypatch.setattr(entry_mod, "load_config", lambda: _cfg(True))
    monkeypatch.setattr(entry_mod, "build_context", lambda **_kw: _ctx())
    monkeypatch.setattr(
        entry_mod,
        "build_snapshot",
        lambda **_kw: SnapshotBuildResult(
            snapshot=CoachSnapshot(
                schema_version=1,
                today="2026-05-15",
                tz="UTC",
                athlete=None,
                plan=None,
                trends=None,
                memory=None,
                working=None,
                omitted_fields=[],
            ),
            trace={"built": True, "enabled": True},
        ),
    )
    monkeypatch.setattr(
        entry_mod,
        "format_snapshot_for_system",
        lambda _snapshot: "\n## Coach Snapshot v1 (authoritative)\n```json\n{}\n```",
    )

    captured = {}

    def _fake_generate(**kw):
        captured.update(kw)
        return ResponderOutput(
            content="Solid run.",
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            cost=0.0,
            model="gpt-4o-mini",
            timings_ms={"run_review_v2_llm_ms": 10.0},
            retried_on_empty=False,
        )

    monkeypatch.setattr(entry_mod, "generate_review", _fake_generate)

    _payload, meta = entry_mod.handle_run_review_turn(
        session=None,
        internal_user_id="u1",
        user_message="How was my run?",
        conversation_history=[],
        anchor_local_date="2026-05-15",
        base_system_content="BASE",
        history_window=8,
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=250,
        response_directive_dialogue={},
        cfg=_cfg(True),
        classifier_result=ClassifierResult(
            is_run_review=True,
            scope="single_run",
            confidence="high",
            source="heuristic",
            reason_code="review_phrase",
        ),
    )
    assert "Coach Snapshot v1" in captured["base_system_content"]
    assert "BASE" in captured["base_system_content"]
    assert meta["coach_context_trace"]["built"] is True
    assert meta["rubric_version"] == "run_review_rubric_v1"
