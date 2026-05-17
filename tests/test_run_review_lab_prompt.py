from __future__ import annotations

from src.smartcoach_mobile_coach.run_review.context_builder import stub_context_for_test
from src.smartcoach_mobile_coach.run_review_lab.prompt import (
    build_run_review_lab_appendix,
)


def test_lab_appendix_includes_data_blocks_without_v2_contract() -> None:
    ctx = stub_context_for_test(
        activity_id=42,
        anchor_local_date="2026-05-17",
        facts={"execution_summary": {"planned": {"type": "easy"}}},
        evidence_pack={"version": "run_review_evidence_pack_v1_easy"},
    )
    appendix = build_run_review_lab_appendix(
        ctx=ctx,
        coach_snapshot={"schema_version": 1, "today": "2026-05-17"},
    )
    assert "## Run review (lab mode)" in appendix
    assert '"run_context"' in appendix
    assert '"coach_snapshot"' in appendix
    assert "## Output format for this turn" not in appendix
    assert "## Coaching Evaluation Rubric" not in appendix
    assert "plain-spoken" in appendix
    assert "last week" in appendix


def test_lab_appendix_omits_card_recap_fields_from_json() -> None:
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
            "hr_drift_summary_display": "![x](kpi-band://yellow)",
            "early_hr": 131.9,
            "late_hr": 137.9,
            "z2_band_pct_display": "85%",
            "pace_spread_sec_per_mi": 18,
        },
        evidence_pack={"version": "run_review_evidence_pack_v1_easy"},
    )
    appendix = build_run_review_lab_appendix(
        ctx=ctx,
        coach_snapshot={"schema_version": 1, "today": "2026-05-17"},
    )
    assert "## Run review (lab mode)" in appendix
    assert "Do not recap the RunSummary card" in appendix
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
    assert "kpi-band://" not in appendix
