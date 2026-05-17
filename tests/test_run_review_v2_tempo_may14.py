"""
Regression: May 14 tempo run prompt + context for Run Review V2.

This is the prime motivating case for V2. The legacy run_recap_fastpath
treats this run like a generic HR-zone summary and advises the athlete
to "dial back effort", which is wrong for a planned tempo. V2 must:

1. Recognize the run as a planned tempo (quality session).
2. Pull splits into the LLM context (mile-by-mile pace + HR is the
   primary evidence for tempo execution).
3. Embed framing that tells the model not to treat the run like an easy
   run and to read execution, not raw intensity.
4. Avoid scare-words like "red zone", "overtraining", "burnout".

We do not assert the LLM *response* here (the LLM is the one producing
the verdict). We assert the **server-side context and prompt** the LLM
sees, which is the actual change V2 introduces.
"""

# pylint: disable=missing-function-docstring,too-many-locals

from __future__ import annotations

import json
from typing import Any, Dict

from src.smartcoach_mobile_coach.run_review.context_builder import (
    _build_workout_intent,
    stub_context_for_test,
)
from src.smartcoach_mobile_coach.run_review.prompt import (
    build_messages,
    build_run_review_system_appendix,
    compact_payload_for_test,
    estimate_appendix_chars,
)


_FORBIDDEN_PHRASES = (
    "red zone",
    "overtraining",
    "burnout",
)


def _may14_facts() -> Dict[str, Any]:
    """Approximate the shape ``tool_get_run_summary.facts`` returns for the
    May 14 tempo run. We only populate what the prompt actually reads;
    extra keys would be ignored downstream."""
    return {
        "title": "Tempo run",
        "distance_display": "6.1 mi",
        "duration_display": "53:14",
        "avg_pace_display": "8:43/mi",
        "avg_heart_rate_display": "151 bpm",
        "max_heart_rate_display": "159 bpm",
        "execution_summary": {
            "plan_status": "executed",
            "violated_rest_day": False,
            "planned": {"type": "tempo", "miles": 6.0},
            "actual": {"type": "tempo", "miles": 6.1},
            "deviation_direction": None,
        },
    }


def _may14_training_kpis() -> Dict[str, Any]:
    return {
        "hr_drift_pct": 5.4,
        "hr_drift_band": "yellow",
        "early_hr": 144,
        "late_hr": 156,
        "peak_split_hr": 159,
        "pace_spread_sec_per_mi": 41,
        "z2_band_pct_display": "32% in Z2",
        "easy_pct_display": "20% easy",
    }


def _may14_zone_bounds() -> Dict[str, Any]:
    return {
        "method": "max_hr_pct",
        "z2_low_bpm": 128,
        "z2_high_bpm": 143,
        "z3_low_bpm": 143,
        "z3_high_bpm": 155,
        "z4_low_bpm": 155,
        "z4_high_bpm": 168,
    }


def _may14_splits() -> Dict[str, Any]:
    """Mile-by-mile rows that capture the actual coaching signal."""
    return {
        "activity_id": 9001,
        "title": "Tempo run",
        "splits_count": 6,
        "splits_total_count": 6,
        "splits_returned": 6,
        "splits_truncated": False,
        "scope": "Each row is one stored lap.",
        "splits": [
            {
                "lap_index": 1,
                "segment_label": "mile 1 (lap 1)",
                "distance_display": "1.0 mi",
                "moving_time_display": "8:50",
                "avg_pace_display": "8:50/mi",
                "avg_heart_rate_display": "138 bpm",
            },
            {
                "lap_index": 2,
                "segment_label": "mile 2 (lap 2)",
                "distance_display": "1.0 mi",
                "moving_time_display": "8:21",
                "avg_pace_display": "8:21/mi",
                "avg_heart_rate_display": "148 bpm",
            },
            {
                "lap_index": 3,
                "segment_label": "mile 3 (lap 3)",
                "distance_display": "1.0 mi",
                "moving_time_display": "8:24",
                "avg_pace_display": "8:24/mi",
                "avg_heart_rate_display": "150 bpm",
            },
            {
                "lap_index": 4,
                "segment_label": "mile 4 (lap 4)",
                "distance_display": "1.0 mi",
                "moving_time_display": "8:26",
                "avg_pace_display": "8:26/mi",
                "avg_heart_rate_display": "150 bpm",
            },
            {
                "lap_index": 5,
                "segment_label": "mile 5 (lap 5)",
                "distance_display": "1.0 mi",
                "moving_time_display": "8:45",
                "avg_pace_display": "8:45/mi",
                "avg_heart_rate_display": "156 bpm",
            },
            {
                "lap_index": 6,
                "segment_label": "mile 6 (lap 6)",
                "distance_display": "1.0 mi",
                "moving_time_display": "9:01",
                "avg_pace_display": "9:01/mi",
                "avg_heart_rate_display": "155 bpm",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Workout-intent derivation
# ---------------------------------------------------------------------------


def test_workout_intent_recognized_as_tempo() -> None:
    intent = _build_workout_intent(_may14_facts())
    assert intent.planned_type == "tempo"
    assert intent.planned_miles == 6.0
    assert intent.plan_status == "executed"
    assert intent.is_quality_session is True
    assert intent.is_easy_or_long is False


# ---------------------------------------------------------------------------
# Compact payload sent to the LLM
# ---------------------------------------------------------------------------


def test_compact_payload_includes_intent_kpis_and_splits() -> None:
    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-14",
        facts=_may14_facts(),
        training_kpis=_may14_training_kpis(),
        zone_bounds=_may14_zone_bounds(),
        splits_payload=_may14_splits(),
        scope="single_run",
        is_easy_run=False,
    )
    compact = compact_payload_for_test(ctx)

    assert compact["activity_id"] == 9001
    assert compact["anchor_local_date"] == "2026-05-14"
    wi = compact["workout_intent"]
    assert wi["planned_type"] == "tempo"
    assert wi["is_quality_session"] is True
    assert compact["training_kpis"]["hr_drift_band"] == "yellow"
    assert compact["zone_bounds"]["z3_high_bpm"] == 155
    # Splits are the key evidence for tempo execution — must be present.
    assert compact["splits_count"] == 6
    assert isinstance(compact["splits"]["splits"], list)
    assert compact["splits"]["splits"][-1]["avg_pace_display"] == "9:01/mi"
    assert compact["is_easy_run"] is False


# ---------------------------------------------------------------------------
# System prompt appendix
# ---------------------------------------------------------------------------


def test_appendix_frames_run_as_quality_session() -> None:
    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-14",
        facts=_may14_facts(),
        training_kpis=_may14_training_kpis(),
        zone_bounds=_may14_zone_bounds(),
        splits_payload=_may14_splits(),
        scope="single_run",
        is_easy_run=False,
    )
    appendix = build_run_review_system_appendix(ctx)

    assert "Completed-run review (RunReview V2)" in appendix
    assert "## Coaching Evaluation Rubric" in appendix
    assert "# Run Review Coaching Rubric v1" in appendix
    assert "## Authoritative `run_facts`" in appendix
    assert '"distance": "6.1 mi"' in appendix
    assert '"max_hr": "159 bpm"' in appendix
    assert "Use the evidence to find the story of the run" in appendix
    assert "Do not merely restate the data" in appendix
    assert "quality session" in appendix.lower()
    # Must instruct grounding in pre-loaded JSON.
    assert "do **not** invent" in appendix.lower()
    # Tells the model not to call tools — this is a one-shot completion.
    assert "do not call any tools" in appendix.lower()


def test_appendix_avoids_scare_words() -> None:
    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-14",
        facts=_may14_facts(),
        training_kpis=_may14_training_kpis(),
        zone_bounds=_may14_zone_bounds(),
        splits_payload=_may14_splits(),
        scope="single_run",
    )
    appendix = build_run_review_system_appendix(ctx).lower()
    for forbidden in _FORBIDDEN_PHRASES:
        # Allow the explicit "never use red zone / overtraining" rule line,
        # but disallow the words used as the model's own framing. We
        # implement this by ensuring the forbidden term appears ONLY in
        # the "Never use scare words" rule sentence.
        occurrences = appendix.count(forbidden)
        assert occurrences == 1, (
            f"Phrase '{forbidden}' should appear exactly once (in the rule "
            f"line), found {occurrences} times. Appendix may be advising the "
            "model to use scare words instead of forbidding them."
        )


def test_appendix_calls_out_splits_when_present() -> None:
    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-14",
        facts=_may14_facts(),
        training_kpis=_may14_training_kpis(),
        zone_bounds=_may14_zone_bounds(),
        splits_payload=_may14_splits(),
        scope="single_run",
    )
    appendix = build_run_review_system_appendix(ctx)
    assert "**Splits:**" in appendix
    assert "splits" in appendix.lower()
    # The embedded JSON must contain the actual lap rows.
    assert "9:01/mi" in appendix


def test_appendix_when_no_splits_does_not_invent_them() -> None:
    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-14",
        facts=_may14_facts(),
        training_kpis=_may14_training_kpis(),
        zone_bounds=_may14_zone_bounds(),
        splits_payload=None,
        scope="single_run",
    )
    appendix = build_run_review_system_appendix(ctx)
    assert "no per-lap data is available" in appendix.lower()
    assert "9:01/mi" not in appendix  # would only be there from splits JSON


def test_appendix_size_is_reasonable() -> None:
    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-14",
        facts=_may14_facts(),
        training_kpis=_may14_training_kpis(),
        zone_bounds=_may14_zone_bounds(),
        splits_payload=_may14_splits(),
        scope="single_run",
    )
    # Keep the additive prompt under ~12 KB to protect latency budgets.
    assert estimate_appendix_chars(ctx) < 12000


# ---------------------------------------------------------------------------
# Final messages array shape
# ---------------------------------------------------------------------------


def test_build_messages_has_single_system_and_trailing_user() -> None:
    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-14",
        facts=_may14_facts(),
        training_kpis=_may14_training_kpis(),
        zone_bounds=_may14_zone_bounds(),
        splits_payload=_may14_splits(),
        scope="single_run",
    )
    messages = build_messages(
        base_system_content="BASE SYSTEM PROMPT",
        ctx=ctx,
        conversation_history=[
            {"role": "user", "content": "hey"},
            {"role": "assistant", "content": "hi"},
        ],
        user_message="how was my tempo today?",
        history_window=10,
    )
    assert messages[0]["role"] == "system"
    assert "BASE SYSTEM PROMPT" in messages[0]["content"]
    assert "Completed-run review (RunReview V2)" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "how was my tempo today?"}
    # Earlier turns are present in order.
    assert messages[1] == {"role": "user", "content": "hey"}
    assert messages[2] == {"role": "assistant", "content": "hi"}


def test_compact_payload_is_valid_json() -> None:
    """The compact dict must be serializable since it gets embedded as JSON."""
    ctx = stub_context_for_test(
        activity_id=9001,
        anchor_local_date="2026-05-14",
        facts=_may14_facts(),
        training_kpis=_may14_training_kpis(),
        zone_bounds=_may14_zone_bounds(),
        splits_payload=_may14_splits(),
        scope="single_run",
    )
    compact = compact_payload_for_test(ctx)
    # Roundtrip serializes cleanly with default=str
    blob = json.dumps(compact, default=str)
    parsed = json.loads(blob)
    assert parsed["workout_intent"]["planned_type"] == "tempo"
