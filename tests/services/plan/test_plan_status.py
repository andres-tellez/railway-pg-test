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
    derive_violated_rest_day,
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


class TestDeriveViolatedRestDay:
    """
    V1.6 §6 derived flag (Phase A item 2).

    Truth table:
      plan_status != UNPLANNED → always False (every non-unplanned
                                 status implies a planned workout → not
                                 a rest day by definition).
      plan_status == UNPLANNED + training_days is None/empty → False
                                 (spec "false otherwise"; safe default
                                 so coach doesn't escalate on ambiguous
                                 plan metadata).
      plan_status == UNPLANNED + weekday IN training_days → False
                                 (day was a scheduled training day but
                                 no PlanWorkout row existed — an
                                 unplanned run on a training day is
                                 a missed-workout-plus-extra, NOT a
                                 rest-day violation).
      plan_status == UNPLANNED + weekday NOT IN training_days → True.
    """

    def test_executed_status_is_never_a_violation(self):
        """Planned + matched run cannot be a rest-day violation."""
        # Even with empty training_days (pathological), a run with a
        # planned workout cannot violate a rest day.
        for td in (
            None,
            [],
            ["Mon"],
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        ):
            assert (
                derive_violated_rest_day(
                    plan_status_value=PlanStatus.EXECUTED,
                    day_weekday=0,
                    plan_training_days=td,
                )
                is False
            )

    def test_planned_only_in_progress_missed_never_violations(self):
        """Any status with a planned workout cannot be a rest-day violation."""
        for status in (
            PlanStatus.PLANNED_ONLY,
            PlanStatus.IN_PROGRESS,
            PlanStatus.MISSED,
        ):
            assert (
                derive_violated_rest_day(
                    plan_status_value=status,
                    day_weekday=6,  # Sunday, often a rest day
                    plan_training_days=["Mon", "Wed", "Thu", "Sat"],
                )
                is False
            ), f"{status} must never surface violated_rest_day=True"

    def test_unplanned_with_no_training_days_defaults_to_false(self):
        """Safe default: can't prove rest-day intent → don't escalate."""
        assert (
            derive_violated_rest_day(
                plan_status_value=PlanStatus.UNPLANNED,
                day_weekday=6,
                plan_training_days=None,
            )
            is False
        )
        # Empty list treated identically.
        assert (
            derive_violated_rest_day(
                plan_status_value=PlanStatus.UNPLANNED,
                day_weekday=6,
                plan_training_days=[],
            )
            is False
        )

    def test_unplanned_on_training_day_is_not_a_violation(self):
        """weekday IS in training_days → missed workout + extra run, not a rest-day violation."""
        # User trains Mon, Wed, Thu, Sat → weekday 0.
        assert (
            derive_violated_rest_day(
                plan_status_value=PlanStatus.UNPLANNED,
                day_weekday=0,  # Mon
                plan_training_days=["Mon", "Wed", "Thu", "Sat"],
            )
            is False
        )

    def test_unplanned_on_non_training_day_is_violation(self):
        """Classic case: runner runs on a planned rest day."""
        # User trains Mon/Wed/Thu/Sat → Sunday (6) is a rest day.
        assert (
            derive_violated_rest_day(
                plan_status_value=PlanStatus.UNPLANNED,
                day_weekday=6,
                plan_training_days=["Mon", "Wed", "Thu", "Sat"],
            )
            is True
        )

    def test_training_days_accepts_full_and_abbreviated_names(self):
        """``DAY_TO_WEEKDAY`` maps both "Monday" and "Mon"."""
        # All-full names.
        assert (
            derive_violated_rest_day(
                plan_status_value=PlanStatus.UNPLANNED,
                day_weekday=6,  # Sunday
                plan_training_days=["Monday", "Wednesday", "Thursday", "Saturday"],
            )
            is True
        )
        # Mixed formats (real legacy data sometimes mixes).
        assert (
            derive_violated_rest_day(
                plan_status_value=PlanStatus.UNPLANNED,
                day_weekday=5,  # Saturday
                plan_training_days=["Mon", "Wednesday", "Thu", "Saturday"],
            )
            is False
        ), "Saturday is a training day whether spelled 'Sat' or 'Saturday'"

    def test_training_days_with_unrecognized_names_are_ignored(self):
        """Unknown tokens must not crash or flip the boolean semantics."""
        assert (
            derive_violated_rest_day(
                plan_status_value=PlanStatus.UNPLANNED,
                day_weekday=6,
                # Known Mon + unknown junk; weekday 6 still not a
                # training day → violation.
                plan_training_days=["Mon", "FunDay", None],  # type: ignore[list-item]
            )
            is True
        )

    def test_all_seven_weekdays_covered_exhaustively(self):
        """Sweep every weekday against a fixed training_days list."""
        training = ["Mon", "Wed", "Thu", "Sat"]
        expected_violation = {
            0: False,  # Mon
            1: True,  # Tue
            2: False,  # Wed
            3: False,  # Thu
            4: True,  # Fri
            5: False,  # Sat
            6: True,  # Sun
        }
        for weekday, expected in expected_violation.items():
            assert (
                derive_violated_rest_day(
                    plan_status_value=PlanStatus.UNPLANNED,
                    day_weekday=weekday,
                    plan_training_days=training,
                )
                is expected
            ), f"weekday={weekday} expected={expected}"


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
