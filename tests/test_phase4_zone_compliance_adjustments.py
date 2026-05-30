from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from src.db.models.activities import Activity
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.services.training_plan.adaptive_adjustment_service import (
    AdaptiveAdjustmentService,
)
from src.smartcoach_mobile_coach.runner_profile.models import (
    PaceZoneBand,
    PaceZoneComputation,
)
from src.services.training_plan.trend_analysis_service import TrendAnalysisResult
from src.services.training_plan.week_analysis_service import (
    WeekAnalysisResult,
    WeekAnalysisService,
)

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_trends() -> TrendAnalysisResult:
    return TrendAnalysisResult(
        volume_trend="stable",
        intensity_trend="stable",
        consistency_trend="stable",
        pace_trend="stable",
        load_trend="stable",
        volume_rolling_avg=95.0,
        intensity_rolling_avg=95.0,
        consistency_rolling_avg=95.0,
        pace_deviation_rolling_avg=0.0,
        load_delta_rolling_avg=0.0,
        has_anomalies=False,
        anomalies=[],
        weeks_analyzed=1,
        week_start_dates=[date(2026, 4, 20)],
    )


def _make_pace_zones() -> PaceZoneComputation:
    return PaceZoneComputation(
        pace_z2=PaceZoneBand(low_sec=560, high_sec=620, display="9:20-10:20/mi"),
        pace_z3=PaceZoneBand(low_sec=520, high_sec=560, display="8:40-9:20/mi"),
        pace_z4=PaceZoneBand(low_sec=440, high_sec=470, display="7:20-7:50/mi"),
        pace_source="test",
        pace_computed_at=datetime.now(timezone.utc),
        marathon_sec=500,
        week1_long_cap=8.0,
    )


def _make_analysis(avg_zone_compliance_by_type: dict[str, float]) -> WeekAnalysisResult:
    return WeekAnalysisResult(
        volume_score=95.0,
        intensity_score=95.0,
        consistency_score=95.0,
        pace_deviation=0.0,
        avg_actual_pace=None,
        avg_planned_pace=None,
        consecutive_missed_days=0,
        fatigue_markers=[],
        current_week_load=220.0,
        previous_week_load=210.0,
        load_delta_pct=4.8,
        pace_threshold=10.0,
        hr_threshold=5.0,
        week_num=8,
        week_start_date=date(2026, 4, 20),
        total_planned_miles=28.0,
        total_actual_miles=27.5,
        planned_workouts=4,
        completed_workouts=4,
        avg_zone_compliance_by_type=avg_zone_compliance_by_type,
    )


def test_calculate_avg_zone_compliance_by_type(test_db_session):
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Phase 4 Aggregation Plan",
        race_date=date(2026, 10, 4),
        race_distance="Marathon",
        is_active=True,
    )
    test_db_session.add(plan)
    test_db_session.flush()
    plan_id = plan.id

    easy_workout = PlanWorkout(
        plan_id=plan.id,
        date=date(2026, 4, 21),
        workout_type="Easy Run",
        description="Easy miles",
        miles=5.0,
        intensity="z2",
        run_type_key="easy",
    )
    long_workout = PlanWorkout(
        plan_id=plan.id,
        date=date(2026, 4, 23),
        workout_type="Long Run",
        description="Long aerobic run",
        miles=10.0,
        intensity="z2",
        run_type_key="long_run",
    )
    test_db_session.add_all([easy_workout, long_workout])
    test_db_session.flush()

    activities = [
        Activity(
            activity_id=991001,
            athlete_id=50001,
            user_id=DEFAULT_USER_ID,
            name="Tuesday easy",
            type="Run",
            start_date=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
            matched_plan_workout_id=easy_workout.id,
            planned_type="easy",
            executed_type="easy",
            zone_compliance_pct=64.0,
            conv_distance=5.0,
            moving_time=2800,
        ),
        Activity(
            activity_id=991002,
            athlete_id=50001,
            user_id=DEFAULT_USER_ID,
            name="Thursday long",
            type="Run",
            start_date=datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc),
            matched_plan_workout_id=long_workout.id,
            planned_type="long",
            executed_type="endurance",
            zone_compliance_pct=58.0,
            conv_distance=10.0,
            moving_time=6200,
        ),
    ]
    test_db_session.add_all(activities)
    test_db_session.commit()

    planned_workouts = (
        test_db_session.query(PlanWorkout)
        .filter(PlanWorkout.plan_id == plan_id)
        .order_by(PlanWorkout.date.asc())
        .all()
    )
    zone_map = WeekAnalysisService._calculate_avg_zone_compliance_by_type(
        session=test_db_session,
        planned_workouts=planned_workouts,
    )

    assert zone_map["easy"] == 64.0
    assert zone_map["long"] == 58.0


def test_calculate_adjustment_applies_zone_compliance_guardrail():
    decision = AdaptiveAdjustmentService.calculate_adjustment(
        analysis=_make_analysis({"easy": 55.0}),
        trends=_make_trends(),
        current_pace_zones=_make_pace_zones(),
        phase="Build",
        weeks_remaining=10,
    )

    assert decision.pace_adjustment_sec >= 5.0
    assert decision.disable_quality_workouts is True
    assert decision.metrics_used["easy_zone_compliance_pct"] == 55.0
    assert decision.metrics_used["easy_min_compliance_pct"] == 60.0
    assert "Low easy-zone compliance" in decision.trigger_reason


def test_calculate_adjustment_skips_guardrail_when_easy_compliance_is_good():
    decision = AdaptiveAdjustmentService.calculate_adjustment(
        analysis=_make_analysis({"easy": 75.0}),
        trends=_make_trends(),
        current_pace_zones=_make_pace_zones(),
        phase="Build",
        weeks_remaining=10,
    )

    assert decision.decision_type == "no_change"
    assert decision.pace_adjustment_sec == 0.0
    assert decision.disable_quality_workouts is False
    assert "easy_zone_compliance_pct" not in decision.metrics_used
