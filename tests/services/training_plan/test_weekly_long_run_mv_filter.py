"""Integrity filters for mv_longest_runs weekly rows used in Pass1."""

from datetime import date

from src.services.training_plan.v2.shared_v2.long_run_signals import (
    filter_mv_weekly_runs_for_planning,
)


def test_filter_drops_anomalous_low_week_vs_median():
    # Mirrors bad MV input [13, 10, 5.01] when real training was ~12–13 mi weeks.
    rows = [
        {
            "week_start": "2025-03-10",
            "date": "2025-03-12",
            "activity_id": 101,
            "distance": 13.0,
        },
        {
            "week_start": "2025-03-03",
            "date": "2025-03-05",
            "activity_id": 102,
            "distance": 10.0,
        },
        {
            "week_start": "2025-02-24",
            "date": "2025-02-26",
            "activity_id": 103,
            "distance": 5.01,
        },
    ]
    out = filter_mv_weekly_runs_for_planning(
        rows, reference_date=date(2025, 3, 20), trace_label="test"
    )
    assert [float(r["distance"]) for r in out] == [13.0, 10.0]


def test_filter_drops_current_week_row():
    ref = date(2025, 3, 12)  # Wednesday; ISO Monday = 2025-03-10
    mon = date(2025, 3, 10)
    rows = [
        {
            "week_start": mon.isoformat(),
            "date": "2025-03-11",
            "activity_id": 201,
            "distance": 5.0,
        },
        {
            "week_start": "2025-03-03",
            "date": "2025-03-04",
            "activity_id": 202,
            "distance": 12.0,
        },
    ]
    out = filter_mv_weekly_runs_for_planning(rows, reference_date=ref)
    assert len(out) == 1
    assert float(out[0]["distance"]) == 12.0


def test_filter_noop_when_too_few_weeks_for_anomaly():
    rows = [
        {"week_start": "2025-03-10", "distance": 13.0, "activity_id": 1},
        {"week_start": "2025-03-03", "distance": 5.01, "activity_id": 2},
    ]
    out = filter_mv_weekly_runs_for_planning(rows, reference_date=date(2025, 3, 20))
    assert len(out) == 2
