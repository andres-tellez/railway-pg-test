from __future__ import annotations

from src.smartcoach_mobile_coach.coach_response.context import stub_context_for_test
from src.smartcoach_mobile_coach.coach_response.prompt import build_appendix


def test_appendix_includes_data_blocks_with_minimal_instruction() -> None:
    ctx = stub_context_for_test(
        activity_id=42,
        anchor_local_date="2026-05-17",
        facts={"execution_summary": {"planned": {"type": "easy"}}},
        evidence_pack={"version": "run_review_evidence_pack_v1_easy"},
    )
    appendix = build_appendix(
        ctx=ctx,
        coach_snapshot={"schema_version": 1, "today": "2026-05-17"},
    )
    assert "## Run review" in appendix
    assert '"run_context"' in appendix
    assert '"coach_snapshot"' in appendix
    assert "teach, do not just recite metrics".lower() in appendix.lower()
    assert "## Coaching Evaluation Rubric" not in appendix
    assert "4–6 short paragraphs" not in appendix


def test_appendix_omits_card_recap_fields_from_json() -> None:
    ctx = stub_context_for_test(
        activity_id=42,
        anchor_local_date="2026-05-17",
        facts={
            "distance_display": "15.0 mi",
            "avg_pace_display": "9:33/mi",
            "avg_heart_rate_display": "135 bpm",
            "max_heart_rate_display": "150 bpm",
            "execution_summary": {"planned": {"type": "easy"}},
        },
        training_kpis={
            "hr_drift_band": "yellow",
            "hr_drift_pct": 4.5,
            "early_hr": 131.9,
            "late_hr": 137.9,
            "z2_band_pct_display": "85%",
            "pace_spread_sec_per_mi": 18,
        },
    )
    appendix = build_appendix(
        ctx=ctx,
        coach_snapshot={"schema_version": 1, "today": "2026-05-17"},
    )
    assert '"training_kpis"' in appendix
    assert '"pace_spread_sec_per_mi"' in appendix
    assert '"distance_display"' not in appendix
    assert '"avg_pace_display"' not in appendix
    assert '"avg_heart_rate_display"' not in appendix
    assert '"max_heart_rate_display"' not in appendix
    assert '"early_hr"' not in appendix
    assert '"late_hr"' not in appendix
    assert '"z2_band_pct_display"' not in appendix
    assert '"hr_drift_pct"' not in appendix
    assert '"hr_drift_band"' not in appendix
