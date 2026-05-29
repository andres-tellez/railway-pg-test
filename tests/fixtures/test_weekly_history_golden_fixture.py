"""Contract fixture for GET /api/training-insights/weekly-history (mobile + backend drift guard)."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE_PATH = Path(__file__).resolve().parent / "weekly_history_golden.json"


def load_weekly_history_golden_fixture() -> dict:
    with FIXTURE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_weekly_history_golden_fixture_shape() -> None:
    payload = load_weekly_history_golden_fixture()
    assert payload["has_history"] is True
    assert payload["latest_week"]["has_insight"] is True
    assert len(payload["latest_week"]["kpis"]) == 4
    assert "easy" in payload["systems"]
    assert "tempo" in payload["systems"]
    assert payload["systems"]["easy"]["insights_easy_banner"]["subtitle"]
    assert (
        payload["systems"]["tempo"]["weekly_data"][0]["tempo_segment_pace_min_per_mi"]
        == 7.25
    )
