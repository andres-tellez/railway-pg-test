"""Emit FE Jest fixtures under smartcoach_mobile (pinned date for stable copy). Run from repo root:

python dev/export_phase8_runner_analysis_fixtures.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_FIXTURES = (
    ROOT.parent
    / "smartcoach_mobile"
    / "smartcoach_app"
    / "__fixtures__"
    / "runner_analysis"
)


class _FixedDate(date):
    @classmethod
    def today(cls):
        return date(2026, 5, 12)


def _wrap(r: dict) -> dict:
    return {
        "pre_generation_runner_review": {
            "plan_generation_readiness": {
                "runner_analysis_display": r["runner_analysis_display"],
            }
        }
    }


def main() -> None:
    sys.path.insert(0, str(ROOT))

    from src.coaching_intelligence.plan_generation_readiness import (
        evaluate_plan_generation_readiness,
    )
    from tests.coaching_intelligence.ambition_gap_fixtures import (
        synthetic_ambition_attributions,
    )

    import src.coaching_intelligence.plan_generation_readiness as pgr

    old_date = pgr.date
    pgr.date = _FixedDate
    try:
        cases: list[tuple[str, dict, dict]] = [
            (
                "just_finish_3d_28mpw",
                {
                    "race_distance": "Marathon",
                    "race_date": "2030-06-01",
                    "primary_goal": "Just Finish",
                    "training_days": ["Mon", "Wed", "Fri"],
                },
                {
                    "activity_summary": {
                        "avg_miles_per_week_approx": 28.0,
                        "longest_run_miles": 10.0,
                        "activities_found": 8,
                        "lookback_weeks": 6,
                        "completed_calendar_weeks_count": 4,
                    },
                    "ambition_gap": {
                        "stance": "COHERENT",
                        "baseline_band": "MODERATE",
                        "goal_demand": "FINISH",
                        "thin_baseline_data": False,
                        "attributions": synthetic_ambition_attributions(
                            baseline_band="MODERATE",
                            goal_demand="FINISH",
                            thin_baseline_data=False,
                            longest_run_miles=10.0,
                        ),
                    },
                    "intake_alignment_state": {
                        "generation_ready": True,
                        "unresolved_flags": [],
                    },
                },
            ),
            (
                "target_time_3h_three_days_24mpw",
                {
                    "race_distance": "Marathon",
                    "race_date": "2030-06-01",
                    "primary_goal": "Target Time",
                    "target_time": "3:00:00",
                    "training_days": ["Mon", "Wed", "Sat"],
                },
                {
                    "activity_summary": {
                        "avg_miles_per_week_approx": 24.0,
                        "longest_run_miles": 12.0,
                        "activities_found": 8,
                        "lookback_weeks": 6,
                        "active_weeks": 4,
                        "completed_calendar_weeks_count": 4,
                    },
                    "ambition_gap": {
                        "stance": "COHERENT",
                        "baseline_band": "MODERATE",
                        "goal_demand": "TIME_TARGET",
                        "thin_baseline_data": False,
                        "attributions": synthetic_ambition_attributions(
                            baseline_band="MODERATE",
                            goal_demand="TIME_TARGET",
                            thin_baseline_data=False,
                            longest_run_miles=12.0,
                        ),
                    },
                    "intake_alignment_state": {
                        "generation_ready": True,
                        "unresolved_flags": [],
                    },
                },
            ),
            (
                "target_time_3h_low_volume_pace_evidence",
                {
                    "race_distance": "Marathon",
                    "race_date": "2030-06-01",
                    "primary_goal": "Target Time",
                    "target_time": "3:30:00",
                    "training_days": ["Tue", "Thu", "Sat"],
                },
                {
                    "activity_summary": {
                        "avg_miles_per_week_approx": 18.0,
                        "longest_run_miles": 8.0,
                        "activities_found": 14,
                        "lookback_weeks": 8,
                        "active_weeks": 6,
                        "completed_calendar_weeks_count": 6,
                        "typical_easy_pace_sec_per_mi": 720.0,
                        "pace_reliability": "medium",
                    },
                    "ambition_gap": {
                        "stance": "COHERENT",
                        "baseline_band": "MODERATE",
                        "goal_demand": "TIME_TARGET",
                        "thin_baseline_data": False,
                        "attributions": synthetic_ambition_attributions(
                            baseline_band="MODERATE",
                            goal_demand="TIME_TARGET",
                            thin_baseline_data=False,
                            longest_run_miles=8.0,
                        ),
                    },
                    "intake_alignment_state": {
                        "generation_ready": True,
                        "unresolved_flags": [],
                    },
                },
            ),
        ]

        MOBILE_FIXTURES.mkdir(parents=True, exist_ok=True)
        for name, plan, assessment in cases:
            r = evaluate_plan_generation_readiness(
                plan_request=plan,
                assessment_api=assessment,
                trace_id=f"fixture-{name}",
            )
            path = MOBILE_FIXTURES / f"{name}.json"
            path.write_text(
                json.dumps(_wrap(r), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print("wrote", path)
    finally:
        pgr.date = old_date


if __name__ == "__main__":
    main()
