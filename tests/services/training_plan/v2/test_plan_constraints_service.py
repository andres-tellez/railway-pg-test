from datetime import date

from src.services.training_plan.v2.plan_constraints_service import (
    PlanConstraintsService,
)


def _build_weeks(count: int) -> list[dict]:
    return [
        {
            "week_number": i + 1,
            "phase": "Base",
            "long_run_miles": 10.0,
        }
        for i in range(count)
    ]


def test_calculate_available_weeks():
    """Test that calculate_available_weeks correctly calculates available training weeks."""
    service = PlanConstraintsService()
    min_start = date(2025, 11, 24)
    race_date = date(2026, 3, 22)

    available_weeks = service.calculate_available_weeks(
        race_date=race_date,
        min_start_date=min_start,
    )

    assert available_weeks == 16


def test_calculate_plan_constraints_validates_recommended_weeks():
    """Test that calculate_plan_constraints validates recommended_weeks (selector already made decision)."""
    service = PlanConstraintsService()
    min_start = date(2025, 11, 24)
    race_date = date(2026, 3, 22)

    # Selector would have recommended 16 weeks (time-aware), so pass that in
    constraints = service.calculate_plan_constraints(
        race_date=race_date,
        recommended_weeks=16,  # Time-aware recommendation from selector
        min_start_date=min_start,
    )

    assert constraints.available_weeks == 16
    assert constraints.recommended_weeks == 16  # Validated, not overridden
    assert constraints.structural_weeks == 16
    assert constraints.target_weeks == 16


def test_calculate_plan_constraints_warns_if_exceeds_available():
    """Test that calculate_plan_constraints warns if recommended_weeks exceeds available_weeks."""
    service = PlanConstraintsService()
    min_start = date(2025, 11, 24)
    race_date = date(2026, 3, 22)

    # This shouldn't happen if selector logic is correct, but test the validation
    constraints = service.calculate_plan_constraints(
        race_date=race_date,
        recommended_weeks=20,  # Exceeds available_weeks (16)
        min_start_date=min_start,
    )

    assert constraints.available_weeks == 16
    assert constraints.recommended_weeks == 16  # Constrained to available_weeks
    assert constraints.target_weeks == 16


def test_align_weeks_with_dates_keeps_start_and_race_week():
    service = PlanConstraintsService()
    min_start = date(2025, 11, 24)
    race_date = date(2026, 3, 22)
    weeks_in = _build_weeks(17)  # 16 training weeks + race week

    weeks_out, aligned_start = service.align_weeks_with_dates(
        weeks=weeks_in,
        race_date=race_date,
        min_start_date=min_start,
    )

    assert aligned_start.isoformat() == "2025-11-24"
    assert weeks_out[0]["week_start_date"] == "2025-11-24"
    assert weeks_out[-1]["week_start_date"] == "2026-03-16"
    assert len(weeks_out) == 17

