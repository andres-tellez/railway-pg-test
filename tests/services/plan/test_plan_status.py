"""
Unit tests for ``src.services.plan.plan_status`` (V1.6 §6, Phase A item 1).

Locks in the deterministic derivation of ``plan_status`` so the LLM
(V1.6 §19) cannot silently drift from the spec. Covers all five enum
values plus the ``None`` empty-day case.
"""

from __future__ import annotations

from datetime import date

from src.services.plan.plan_status import (
    PlanStatus,
    plan_status_for_activity,
    plan_status_for_day,
)


class TestPlanStatusEnumValues:
    """Enum string values are part of the wire contract — lock them."""

    def test_enum_values_match_spec(self):
        assert PlanStatus.PLANNED_ONLY.value == "planned_only"
        assert PlanStatus.IN_PROGRESS.value == "in_progress"
        assert PlanStatus.EXECUTED.value == "executed"
        assert PlanStatus.MISSED.value == "missed"
        assert PlanStatus.UNPLANNED.value == "unplanned"

    def test_exactly_five_values(self):
        """Any new state must be added to the spec first, then here."""
        assert len(list(PlanStatus)) == 5

    def test_str_enum_serializes_to_value(self):
        """``str, Enum`` base makes JSON.dumps emit the value string."""
        import json

        assert json.dumps(PlanStatus.EXECUTED.value) == '"executed"'


class TestPlanStatusForActivity:
    """Per-activity pairing: binary executed / unplanned."""

    def test_matched_activity_is_executed(self):
        assert plan_status_for_activity(42) == PlanStatus.EXECUTED

    def test_matched_activity_with_zero_id_is_executed(self):
        """Zero is a valid FK; only ``None`` means unlinked."""
        assert plan_status_for_activity(0) == PlanStatus.EXECUTED

    def test_unlinked_activity_is_unplanned(self):
        assert plan_status_for_activity(None) == PlanStatus.UNPLANNED


class TestPlanStatusForDayFullMatrix:
    """All 5 V1.6 §6 states + the empty-day ``None`` case."""

    TODAY = date(2026, 4, 21)

    def test_planned_and_matched_is_executed(self):
        """Regardless of temporal position, planned+matched → executed."""
        for d in (date(2026, 4, 20), self.TODAY, date(2026, 4, 22)):
            assert (
                plan_status_for_day(
                    has_planned_workout=True,
                    has_matching_activity=True,
                    day_date=d,
                    today=self.TODAY,
                )
                == PlanStatus.EXECUTED
            ), f"day={d} must be EXECUTED when planned and matched"

    def test_planned_no_activity_future_is_planned_only(self):
        assert (
            plan_status_for_day(
                has_planned_workout=True,
                has_matching_activity=False,
                day_date=date(2026, 4, 25),
                today=self.TODAY,
            )
            == PlanStatus.PLANNED_ONLY
        )

    def test_planned_no_activity_today_is_in_progress(self):
        assert (
            plan_status_for_day(
                has_planned_workout=True,
                has_matching_activity=False,
                day_date=self.TODAY,
                today=self.TODAY,
            )
            == PlanStatus.IN_PROGRESS
        )

    def test_planned_no_activity_past_is_missed(self):
        assert (
            plan_status_for_day(
                has_planned_workout=True,
                has_matching_activity=False,
                day_date=date(2026, 4, 18),
                today=self.TODAY,
            )
            == PlanStatus.MISSED
        )

    def test_unplanned_activity_is_unplanned(self):
        """No plan but activity exists → unplanned (regardless of day)."""
        for d in (date(2026, 4, 18), self.TODAY, date(2026, 4, 25)):
            assert (
                plan_status_for_day(
                    has_planned_workout=False,
                    has_matching_activity=True,
                    day_date=d,
                    today=self.TODAY,
                )
                == PlanStatus.UNPLANNED
            ), f"day={d} must be UNPLANNED when no plan but activity"

    def test_empty_day_returns_none(self):
        """No plan, no activity → None (spec does not enumerate a status)."""
        assert (
            plan_status_for_day(
                has_planned_workout=False,
                has_matching_activity=False,
                day_date=date(2026, 4, 18),
                today=self.TODAY,
            )
            is None
        )

    def test_invariant_planned_day_always_has_status(self):
        """Any day with a planned workout yields a non-None status."""
        for d in (date(2026, 4, 18), self.TODAY, date(2026, 4, 25)):
            for matched in (True, False):
                assert (
                    plan_status_for_day(
                        has_planned_workout=True,
                        has_matching_activity=matched,
                        day_date=d,
                        today=self.TODAY,
                    )
                    is not None
                )


class TestPlanStatusDocumentedGapAcknowledged:
    """
    Guard comment: current-week does not surface unplanned-day pairings
    because its day list is driven by planned workouts. This test
    documents that understanding at the producer level.
    """

    def test_day_view_supports_unplanned(self):
        """Producer is ready for Phase B ``get_weekly_plan`` to pass
        ``has_planned_workout=False, has_matching_activity=True`` on
        unplanned days — it must return UNPLANNED, not None."""
        assert (
            plan_status_for_day(
                has_planned_workout=False,
                has_matching_activity=True,
                day_date=date(2026, 4, 19),
                today=date(2026, 4, 21),
            )
            == PlanStatus.UNPLANNED
        )
