from datetime import date, datetime, timezone
import uuid

from src.db.models.activities import Activity
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.services.run_execution_analysis_service import (
    analyze_activity_execution,
    analyze_recent_activity_window,
)
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    normalize_run_type_key,
)


def _seed_active_plan_with_workout(session, *, user_id: uuid.UUID, workout_date: date):
    session.add(
        UserAthleteLink(
            user_id=str(user_id),
            athlete_id=12345,
        )
    )
    plan = Plan(
        user_id=user_id,
        plan_name="Test Plan",
        race_date=workout_date,
        race_distance="Marathon",
        is_active=True,
    )
    session.add(plan)
    session.flush()

    workout = PlanWorkout(
        plan_id=plan.id,
        date=workout_date,
        workout_type="Easy Run",
        description="Keep it easy",
        miles=6.0,
        intensity="z2",
        run_type_key="easy",
    )
    session.add(workout)
    session.commit()
    return workout


def test_analyze_activity_execution_matches_plan_and_scores(test_db_session):
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    workout_date = date(2026, 4, 18)
    workout = _seed_active_plan_with_workout(
        test_db_session, user_id=user_id, workout_date=workout_date
    )

    activity = Activity(
        activity_id=90001,
        athlete_id=12345,
        user_id=user_id,
        name="Saturday Run",
        type="Run",
        start_date=datetime(2026, 4, 18, 14, 0, tzinfo=timezone.utc),
        timezone="(GMT-04:00) America/New_York",
        conv_distance=6.0,
        hr_zone_1=42.0,
        hr_zone_2=44.0,
        hr_zone_3=10.0,
        hr_zone_4=4.0,
        hr_zone_5=0.0,
    )
    test_db_session.add(activity)
    test_db_session.commit()

    result = analyze_activity_execution(test_db_session, activity, commit=True)
    assert result is not None
    assert result["executed_type"] == "easy"
    assert activity.matched_plan_workout_id == workout.id
    assert activity.planned_type == "easy"
    assert activity.run_score in ("green", "yellow")
    assert activity.zone_compliance_pct is not None
    assert activity.completion_pct == 100.0


def test_analyze_recent_activity_window_updates_runs(test_db_session):
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    workout_date = date(2026, 4, 17)
    _seed_active_plan_with_workout(
        test_db_session, user_id=user_id, workout_date=workout_date
    )

    activity = Activity(
        activity_id=90002,
        athlete_id=12345,
        user_id=user_id,
        name="Friday Run",
        type="Run",
        start_date=datetime(2026, 4, 17, 15, 0, tzinfo=timezone.utc),
        timezone="UTC",
        conv_distance=5.4,
        hr_zone_1=18.0,
        hr_zone_2=22.0,
        hr_zone_3=35.0,
        hr_zone_4=20.0,
        hr_zone_5=5.0,
    )
    test_db_session.add(activity)
    test_db_session.commit()

    updated = analyze_recent_activity_window(
        test_db_session,
        athlete_id=12345,
        user_id=str(user_id),
        after_ts=int(datetime(2026, 4, 17, 0, 0, tzinfo=timezone.utc).timestamp()),
        before_ts=int(datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc).timestamp()),
        limit=20,
    )
    assert updated >= 1

    refreshed = (
        test_db_session.query(Activity).filter(Activity.activity_id == 90002).first()
    )
    assert refreshed is not None
    assert refreshed.executed_type is not None
    assert refreshed.run_score in ("green", "yellow", "red")


def test_normalize_run_type_key_maps_legacy_values():
    assert normalize_run_type_key("endurance") == "long"
    assert normalize_run_type_key("threshold") == "tempo"
    assert normalize_run_type_key("recovery") == "recovery"


def test_plan_mismatch_applies_score_penalty(test_db_session):
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    workout_date = date(2026, 4, 19)
    _seed_active_plan_with_workout(
        test_db_session, user_id=user_id, workout_date=workout_date
    )

    activity = Activity(
        activity_id=90003,
        athlete_id=12345,
        user_id=user_id,
        name="Too Hard Day",
        type="Run",
        start_date=datetime(2026, 4, 19, 13, 0, tzinfo=timezone.utc),
        timezone="UTC",
        conv_distance=6.2,
        hr_zone_1=2.0,
        hr_zone_2=8.0,
        hr_zone_3=56.0,
        hr_zone_4=30.0,
        hr_zone_5=4.0,
    )
    test_db_session.add(activity)
    test_db_session.commit()

    out = analyze_activity_execution(test_db_session, activity, commit=True)
    assert out is not None
    assert activity.planned_type == "easy"
    assert activity.executed_type in ("steady", "tempo")
    assert activity.run_score == "red"
    detail = activity.scoring_detail or {}
    selection = detail.get("selection") or {}
    assert selection.get("mismatch_penalty_reason") in (
        "mismatch_strong",
        "mismatch_moderate",
    )
