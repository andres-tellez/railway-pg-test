#!/usr/bin/env python3
"""
Migrate all data for athlete_id 155302 from production to local.

This script copies all data associated with athlete_id 155302 and maps it
to the local test account's athlete_id (347085).
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import traceback

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Load environment
env_local = Path(".env.local")
if env_local.exists():
    load_dotenv(env_local, override=False)

prod_db_url = os.getenv("PROD_DATABASE_URL") or os.getenv("DATABASE_URL")
local_db_url = os.getenv("DATABASE_URL")

if not prod_db_url or not local_db_url:
    print("❌ Database URLs not set")
    sys.exit(1)

# Athlete IDs
source_athlete_id = 347085  # Production athlete_id to copy
target_athlete_id = 347085  # Local test account athlete_id (same ID)

print("=" * 60)
print(f"🔄 Migrating athlete_id {source_athlete_id} → {target_athlete_id}")
print("=" * 60)

try:
    prod_engine = create_engine(prod_db_url, echo=False)
    local_engine = create_engine(local_db_url, echo=False)
    prod_session = sessionmaker(bind=prod_engine)()
    local_session = sessionmaker(bind=local_engine)()

    # Get source user_id
    print("\n1. Finding source user_id...")
    result = prod_session.execute(
        text("SELECT user_id FROM user_athletes WHERE athlete_id = :athlete_id"),
        {"athlete_id": source_athlete_id},
    )
    source_user_row = result.fetchone()
    if not source_user_row:
        print(f"❌ No user_athletes record found for athlete_id {source_athlete_id}")
        sys.exit(1)
    source_user_id = str(source_user_row[0])
    print(f"   ✅ Found user_id: {source_user_id}")

    # Get target user_id
    print("\n2. Finding target user_id...")
    result = local_session.execute(
        text("SELECT user_id FROM user_athletes WHERE athlete_id = :athlete_id"),
        {"athlete_id": target_athlete_id},
    )
    target_user_row = result.fetchone()
    if not target_user_row:
        print(f"❌ No user_athletes record found for athlete_id {target_athlete_id}")
        print("   Make sure your test account is connected in local database")
        sys.exit(1)
    target_user_id = str(target_user_row[0])
    print(f"   ✅ Found user_id: {target_user_id}")

    # Check what data exists
    print("\n3. Checking source data...")
    result = prod_session.execute(
        text("SELECT COUNT(*) FROM activities WHERE athlete_id = :athlete_id"),
        {"athlete_id": source_athlete_id},
    )
    activity_count = result.fetchone()[0]
    print(f"   Activities: {activity_count}")

    result = prod_session.execute(
        text("SELECT COUNT(*) FROM plans WHERE user_id = :user_id"),
        {"user_id": source_user_id},
    )
    plan_count = result.fetchone()[0]
    print(f"   Plans: {plan_count}")

    result = prod_session.execute(
        text(
            "SELECT COUNT(*) FROM splits WHERE activity_id IN (SELECT activity_id FROM activities WHERE athlete_id = :athlete_id)"
        ),
        {"athlete_id": source_athlete_id},
    )
    split_count = result.fetchone()[0]
    print(f"   Splits: {split_count}")

    # Migrate activities
    print("\n4. Migrating activities...")
    activities = prod_session.execute(
        text("SELECT * FROM activities WHERE athlete_id = :athlete_id"),
        {"athlete_id": source_athlete_id},
    ).fetchall()

    migrated_activities = 0
    for activity in activities:
        # Check if exists
        existing = local_session.execute(
            text("SELECT activity_id FROM activities WHERE activity_id = :activity_id"),
            {"activity_id": activity.activity_id},
        ).fetchone()

        if existing:
            # Update
            local_session.execute(
                text(
                    """
                    UPDATE activities
                    SET athlete_id = :athlete_id, user_id = :user_id,
                        name = :name, type = :type, start_date = :start_date,
                        distance = :distance, elapsed_time = :elapsed_time,
                        moving_time = :moving_time, total_elevation_gain = :total_elevation_gain,
                        external_id = :external_id, timezone = :timezone,
                        average_speed = :average_speed, max_speed = :max_speed,
                        suffer_score = :suffer_score, average_heartrate = :average_heartrate,
                        max_heartrate = :max_heartrate, calories = :calories,
                        conv_distance = :conv_distance, conv_elevation_feet = :conv_elevation_feet,
                        conv_avg_speed = :conv_avg_speed, conv_max_speed = :conv_max_speed,
                        conv_moving_time = :conv_moving_time, conv_elapsed_time = :conv_elapsed_time,
                        hr_zone_1 = :hr_zone_1, hr_zone_2 = :hr_zone_2,
                        hr_zone_3 = :hr_zone_3, hr_zone_4 = :hr_zone_4, hr_zone_5 = :hr_zone_5
                    WHERE activity_id = :activity_id
                """
                ),
                {
                    "activity_id": activity.activity_id,
                    "athlete_id": target_athlete_id,
                    "user_id": target_user_id,
                    "name": activity.name,
                    "type": activity.type,
                    "start_date": activity.start_date,
                    "distance": activity.distance,
                    "elapsed_time": activity.elapsed_time,
                    "moving_time": activity.moving_time,
                    "total_elevation_gain": activity.total_elevation_gain,
                    "external_id": activity.external_id,
                    "timezone": activity.timezone,
                    "average_speed": activity.average_speed,
                    "max_speed": activity.max_speed,
                    "suffer_score": activity.suffer_score,
                    "average_heartrate": activity.average_heartrate,
                    "max_heartrate": activity.max_heartrate,
                    "calories": activity.calories,
                    "conv_distance": activity.conv_distance,
                    "conv_elevation_feet": activity.conv_elevation_feet,
                    "conv_avg_speed": activity.conv_avg_speed,
                    "conv_max_speed": activity.conv_max_speed,
                    "conv_moving_time": activity.conv_moving_time,
                    "conv_elapsed_time": activity.conv_elapsed_time,
                    "hr_zone_1": activity.hr_zone_1,
                    "hr_zone_2": activity.hr_zone_2,
                    "hr_zone_3": activity.hr_zone_3,
                    "hr_zone_4": activity.hr_zone_4,
                    "hr_zone_5": activity.hr_zone_5,
                },
            )
        else:
            # Insert
            local_session.execute(
                text(
                    """
                    INSERT INTO activities (
                        activity_id, athlete_id, user_id, name, type, start_date,
                        distance, elapsed_time, moving_time, total_elevation_gain,
                        external_id, timezone, average_speed, max_speed,
                        suffer_score, average_heartrate, max_heartrate, calories,
                        conv_distance, conv_elevation_feet, conv_avg_speed,
                        conv_max_speed, conv_moving_time, conv_elapsed_time,
                        hr_zone_1, hr_zone_2, hr_zone_3, hr_zone_4, hr_zone_5
                    ) VALUES (
                        :activity_id, :athlete_id, :user_id, :name, :type, :start_date,
                        :distance, :elapsed_time, :moving_time, :total_elevation_gain,
                        :external_id, :timezone, :average_speed, :max_speed,
                        :suffer_score, :average_heartrate, :max_heartrate, :calories,
                        :conv_distance, :conv_elevation_feet, :conv_avg_speed,
                        :conv_max_speed, :conv_moving_time, :conv_elapsed_time,
                        :hr_zone_1, :hr_zone_2, :hr_zone_3, :hr_zone_4, :hr_zone_5
                    )
                """
                ),
                {
                    "activity_id": activity.activity_id,
                    "athlete_id": target_athlete_id,
                    "user_id": target_user_id,
                    "name": activity.name,
                    "type": activity.type,
                    "start_date": activity.start_date,
                    "distance": activity.distance,
                    "elapsed_time": activity.elapsed_time,
                    "moving_time": activity.moving_time,
                    "total_elevation_gain": activity.total_elevation_gain,
                    "external_id": activity.external_id,
                    "timezone": activity.timezone,
                    "average_speed": activity.average_speed,
                    "max_speed": activity.max_speed,
                    "suffer_score": activity.suffer_score,
                    "average_heartrate": activity.average_heartrate,
                    "max_heartrate": activity.max_heartrate,
                    "calories": activity.calories,
                    "conv_distance": activity.conv_distance,
                    "conv_elevation_feet": activity.conv_elevation_feet,
                    "conv_avg_speed": activity.conv_avg_speed,
                    "conv_max_speed": activity.conv_max_speed,
                    "conv_moving_time": activity.conv_moving_time,
                    "conv_elapsed_time": activity.conv_elapsed_time,
                    "hr_zone_1": activity.hr_zone_1,
                    "hr_zone_2": activity.hr_zone_2,
                    "hr_zone_3": activity.hr_zone_3,
                    "hr_zone_4": activity.hr_zone_4,
                    "hr_zone_5": activity.hr_zone_5,
                },
            )
        migrated_activities += 1

    local_session.commit()
    print(f"   ✅ Migrated {migrated_activities} activities")

    # Migrate splits
    print("\n5. Migrating splits...")
    activity_ids = [a.activity_id for a in activities]
    total_splits = 0

    for activity_id in activity_ids:
        splits = prod_session.execute(
            text("SELECT * FROM splits WHERE activity_id = :activity_id"),
            {"activity_id": activity_id},
        ).fetchall()

        for split in splits:
            existing = local_session.execute(
                text(
                    "SELECT id FROM splits WHERE activity_id = :activity_id AND lap_index = :lap_index"
                ),
                {"activity_id": split.activity_id, "lap_index": split.lap_index},
            ).fetchone()

            if existing:
                local_session.execute(
                    text(
                        """
                        UPDATE splits
                        SET distance = :distance, elapsed_time = :elapsed_time,
                            moving_time = :moving_time, average_speed = :average_speed,
                            max_speed = :max_speed, start_index = :start_index,
                            end_index = :end_index, split = :split,
                            average_heartrate = :average_heartrate, pace_zone = :pace_zone,
                            conv_distance = :conv_distance, conv_avg_speed = :conv_avg_speed,
                            conv_moving_time = :conv_moving_time, conv_elapsed_time = :conv_elapsed_time
                        WHERE activity_id = :activity_id AND lap_index = :lap_index
                    """
                    ),
                    {
                        "activity_id": split.activity_id,
                        "lap_index": split.lap_index,
                        "distance": split.distance,
                        "elapsed_time": split.elapsed_time,
                        "moving_time": split.moving_time,
                        "average_speed": split.average_speed,
                        "max_speed": split.max_speed,
                        "start_index": split.start_index,
                        "end_index": split.end_index,
                        "split": split.split,
                        "average_heartrate": split.average_heartrate,
                        "pace_zone": split.pace_zone,
                        "conv_distance": split.conv_distance,
                        "conv_avg_speed": split.conv_avg_speed,
                        "conv_moving_time": split.conv_moving_time,
                        "conv_elapsed_time": split.conv_elapsed_time,
                    },
                )
            else:
                local_session.execute(
                    text(
                        """
                        INSERT INTO splits (
                            activity_id, lap_index, distance, elapsed_time,
                            moving_time, average_speed, max_speed,
                            start_index, end_index, split, average_heartrate,
                            pace_zone, conv_distance, conv_avg_speed,
                            conv_moving_time, conv_elapsed_time
                        ) VALUES (
                            :activity_id, :lap_index, :distance, :elapsed_time,
                            :moving_time, :average_speed, :max_speed,
                            :start_index, :end_index, :split, :average_heartrate,
                            :pace_zone, :conv_distance, :conv_avg_speed,
                            :conv_moving_time, :conv_elapsed_time
                        )
                    """
                    ),
                    {
                        "activity_id": split.activity_id,
                        "lap_index": split.lap_index,
                        "distance": split.distance,
                        "elapsed_time": split.elapsed_time,
                        "moving_time": split.moving_time,
                        "average_speed": split.average_speed,
                        "max_speed": split.max_speed,
                        "start_index": split.start_index,
                        "end_index": split.end_index,
                        "split": split.split,
                        "average_heartrate": split.average_heartrate,
                        "pace_zone": split.pace_zone,
                        "conv_distance": split.conv_distance,
                        "conv_avg_speed": split.conv_avg_speed,
                        "conv_moving_time": split.conv_moving_time,
                        "conv_elapsed_time": split.conv_elapsed_time,
                    },
                )
            total_splits += 1

    local_session.commit()
    print(f"   ✅ Migrated {total_splits} splits")

    # Migrate plans
    print("\n6. Migrating plans...")
    plans = prod_session.execute(
        text("SELECT * FROM plans WHERE user_id = :user_id"),
        {"user_id": source_user_id},
    ).fetchall()

    plan_id_map = {}
    for plan in plans:
        # Convert JSON fields to strings if needed
        race_metadata = plan.race_metadata
        if isinstance(race_metadata, dict):
            race_metadata = json.dumps(race_metadata)

        # training_days is a PostgreSQL ARRAY, so keep it as a list
        training_days = plan.training_days

        result = local_session.execute(
            text(
                """
                INSERT INTO plans (
                    user_id, plan_name, race_date, race_distance, race_name,
                    race_location, race_metadata, primary_goal, target_time,
                    training_days, notes, is_active, created_by, created_at
                ) VALUES (
                    :user_id, :plan_name, :race_date, :race_distance, :race_name,
                    :race_location, :race_metadata, :primary_goal, :target_time,
                    :training_days, :notes, :is_active, :created_by, :created_at
                )
                RETURNING id
            """
            ),
            {
                "user_id": target_user_id,
                "plan_name": plan.plan_name,
                "race_date": plan.race_date,
                "race_distance": plan.race_distance,
                "race_name": plan.race_name,
                "race_location": plan.race_location,
                "race_metadata": race_metadata,
                "primary_goal": plan.primary_goal,
                "target_time": plan.target_time,
                "training_days": training_days,
                "notes": plan.notes,
                "is_active": plan.is_active,
                "created_by": plan.created_by,
                "created_at": plan.created_at,
            },
        )
        new_plan_id = result.fetchone()[0]
        plan_id_map[plan.id] = new_plan_id

    local_session.commit()
    print(f"   ✅ Migrated {len(plans)} plans")

    # Migrate plan_workouts
    if plan_id_map:
        print("\n7. Migrating plan_workouts...")
        total_workouts = 0
        for prod_plan_id, local_plan_id in plan_id_map.items():
            workouts = prod_session.execute(
                text("SELECT * FROM plan_workouts WHERE plan_id = :plan_id"),
                {"plan_id": prod_plan_id},
            ).fetchall()

            for workout in workouts:
                existing = local_session.execute(
                    text(
                        "SELECT id FROM plan_workouts WHERE plan_id = :plan_id AND date = :date"
                    ),
                    {"plan_id": local_plan_id, "date": workout.date},
                ).fetchone()

                if existing:
                    local_session.execute(
                        text(
                            """
                            UPDATE plan_workouts
                            SET workout_type = :workout_type, description = :description,
                                miles = :miles, intensity = :intensity, target_zone = :target_zone,
                                target_hr = :target_hr, focus = :focus, segments = :segments,
                                run_type_key = :run_type_key, phase = :phase,
                                pace_ranges = :pace_ranges, allow_quality = :allow_quality,
                                cues = :cues, quality_insert = :quality_insert
                            WHERE plan_id = :plan_id AND date = :date
                        """
                        ),
                        {
                            "plan_id": local_plan_id,
                            "date": workout.date,
                            "workout_type": workout.workout_type,
                            "description": workout.description,
                            "miles": workout.miles,
                            "intensity": workout.intensity,
                            "target_zone": workout.target_zone,
                            "target_hr": workout.target_hr,
                            "focus": workout.focus,
                            "segments": (
                                json.dumps(workout.segments)
                                if isinstance(workout.segments, dict)
                                else workout.segments
                            ),
                            "run_type_key": workout.run_type_key,
                            "phase": workout.phase,
                            "pace_ranges": (
                                json.dumps(workout.pace_ranges)
                                if isinstance(workout.pace_ranges, dict)
                                else workout.pace_ranges
                            ),
                            "allow_quality": workout.allow_quality,
                            "cues": workout.cues,
                            "quality_insert": (
                                json.dumps(workout.quality_insert)
                                if isinstance(workout.quality_insert, dict)
                                else workout.quality_insert
                            ),
                        },
                    )
                else:
                    local_session.execute(
                        text(
                            """
                            INSERT INTO plan_workouts (
                                plan_id, date, workout_type, description, miles,
                                intensity, target_zone, target_hr, focus, segments,
                                run_type_key, phase, pace_ranges, allow_quality,
                                cues, quality_insert
                            ) VALUES (
                                :plan_id, :date, :workout_type, :description, :miles,
                                :intensity, :target_zone, :target_hr, :focus, :segments,
                                :run_type_key, :phase, :pace_ranges, :allow_quality,
                                :cues, :quality_insert
                            )
                        """
                        ),
                        {
                            "plan_id": local_plan_id,
                            "date": workout.date,
                            "workout_type": workout.workout_type,
                            "description": workout.description,
                            "miles": workout.miles,
                            "intensity": workout.intensity,
                            "target_zone": workout.target_zone,
                            "target_hr": workout.target_hr,
                            "focus": workout.focus,
                            "segments": (
                                json.dumps(workout.segments)
                                if isinstance(workout.segments, dict)
                                else workout.segments
                            ),
                            "run_type_key": workout.run_type_key,
                            "phase": workout.phase,
                            "pace_ranges": (
                                json.dumps(workout.pace_ranges)
                                if isinstance(workout.pace_ranges, dict)
                                else workout.pace_ranges
                            ),
                            "allow_quality": workout.allow_quality,
                            "cues": workout.cues,
                            "quality_insert": (
                                json.dumps(workout.quality_insert)
                                if isinstance(workout.quality_insert, dict)
                                else workout.quality_insert
                            ),
                        },
                    )
                total_workouts += 1

        local_session.commit()
        print(f"   ✅ Migrated {total_workouts} plan_workouts")

    # Migrate weekly_metrics
    if plan_id_map:
        print("\n8. Migrating weekly_metrics...")
        total_metrics = 0
        for prod_plan_id, local_plan_id in plan_id_map.items():
            metrics = prod_session.execute(
                text("SELECT * FROM weekly_metrics WHERE plan_id = :plan_id"),
                {"plan_id": prod_plan_id},
            ).fetchall()

            for metric in metrics:
                existing = local_session.execute(
                    text(
                        "SELECT id FROM weekly_metrics WHERE plan_id = :plan_id AND week_num = :week_num"
                    ),
                    {"plan_id": local_plan_id, "week_num": metric.week_num},
                ).fetchone()

                if existing:
                    local_session.execute(
                        text(
                            """
                            UPDATE weekly_metrics
                            SET week_start_date = :week_start_date,
                                volume_score = :volume_score, intensity_score = :intensity_score,
                                consistency_score = :consistency_score, pace_deviation = :pace_deviation,
                                avg_actual_pace = :avg_actual_pace, avg_planned_pace = :avg_planned_pace,
                                consecutive_missed_days = :consecutive_missed_days,
                                current_week_load = :current_week_load,
                                previous_week_load = :previous_week_load,
                                load_delta_pct = :load_delta_pct, pace_threshold = :pace_threshold,
                                hr_threshold = :hr_threshold, match_score = :match_score,
                                context_score = :context_score, phase = :phase,
                                weeks_remaining = :weeks_remaining
                            WHERE plan_id = :plan_id AND week_num = :week_num
                        """
                        ),
                        {
                            "plan_id": local_plan_id,
                            "week_num": metric.week_num,
                            "week_start_date": metric.week_start_date,
                            "volume_score": metric.volume_score,
                            "intensity_score": metric.intensity_score,
                            "consistency_score": metric.consistency_score,
                            "pace_deviation": metric.pace_deviation,
                            "avg_actual_pace": metric.avg_actual_pace,
                            "avg_planned_pace": metric.avg_planned_pace,
                            "consecutive_missed_days": metric.consecutive_missed_days,
                            "current_week_load": metric.current_week_load,
                            "previous_week_load": metric.previous_week_load,
                            "load_delta_pct": metric.load_delta_pct,
                            "pace_threshold": metric.pace_threshold,
                            "hr_threshold": metric.hr_threshold,
                            "match_score": metric.match_score,
                            "context_score": (
                                json.dumps(metric.context_score)
                                if isinstance(metric.context_score, dict)
                                else metric.context_score
                            ),
                            "phase": metric.phase,
                            "weeks_remaining": metric.weeks_remaining,
                        },
                    )
                else:
                    local_session.execute(
                        text(
                            """
                            INSERT INTO weekly_metrics (
                                plan_id, week_num, week_start_date,
                                volume_score, intensity_score, consistency_score,
                                pace_deviation, avg_actual_pace, avg_planned_pace,
                                consecutive_missed_days, current_week_load,
                                previous_week_load, load_delta_pct,
                                pace_threshold, hr_threshold, match_score,
                                context_score, phase, weeks_remaining
                            ) VALUES (
                                :plan_id, :week_num, :week_start_date,
                                :volume_score, :intensity_score, :consistency_score,
                                :pace_deviation, :avg_actual_pace, :avg_planned_pace,
                                :consecutive_missed_days, :current_week_load,
                                :previous_week_load, :load_delta_pct,
                                :pace_threshold, :hr_threshold, :match_score,
                                :context_score, :phase, :weeks_remaining
                            )
                        """
                        ),
                        {
                            "plan_id": local_plan_id,
                            "week_num": metric.week_num,
                            "week_start_date": metric.week_start_date,
                            "volume_score": metric.volume_score,
                            "intensity_score": metric.intensity_score,
                            "consistency_score": metric.consistency_score,
                            "pace_deviation": metric.pace_deviation,
                            "avg_actual_pace": metric.avg_actual_pace,
                            "avg_planned_pace": metric.avg_planned_pace,
                            "consecutive_missed_days": metric.consecutive_missed_days,
                            "current_week_load": metric.current_week_load,
                            "previous_week_load": metric.previous_week_load,
                            "load_delta_pct": metric.load_delta_pct,
                            "pace_threshold": metric.pace_threshold,
                            "hr_threshold": metric.hr_threshold,
                            "match_score": metric.match_score,
                            "context_score": (
                                json.dumps(metric.context_score)
                                if isinstance(metric.context_score, dict)
                                else metric.context_score
                            ),
                            "phase": metric.phase,
                            "weeks_remaining": metric.weeks_remaining,
                        },
                    )
                total_metrics += 1

        local_session.commit()
        print(f"   ✅ Migrated {total_metrics} weekly_metrics")

    # Migrate weekly_decision_log
    if plan_id_map:
        print("\n9. Migrating weekly_decision_log...")
        total_logs = 0
        for prod_plan_id, local_plan_id in plan_id_map.items():
            logs = prod_session.execute(
                text("SELECT * FROM weekly_decision_log WHERE plan_id = :plan_id"),
                {"plan_id": prod_plan_id},
            ).fetchall()

            for log in logs:
                existing = local_session.execute(
                    text(
                        "SELECT id FROM weekly_decision_log WHERE plan_id = :plan_id AND week_num = :week_num"
                    ),
                    {"plan_id": local_plan_id, "week_num": log.week_num},
                ).fetchone()

                if existing:
                    local_session.execute(
                        text(
                            """
                            UPDATE weekly_decision_log
                            SET week_start_date = :week_start_date,
                                decision_type = :decision_type, trigger_reason = :trigger_reason,
                                metrics_json = :metrics_json, adjustments_json = :adjustments_json,
                                match_score = :match_score, phase = :phase,
                                weeks_remaining = :weeks_remaining
                            WHERE plan_id = :plan_id AND week_num = :week_num
                        """
                        ),
                        {
                            "plan_id": local_plan_id,
                            "week_num": log.week_num,
                            "week_start_date": log.week_start_date,
                            "decision_type": log.decision_type,
                            "trigger_reason": log.trigger_reason,
                            "metrics_json": (
                                json.dumps(log.metrics_json)
                                if isinstance(log.metrics_json, dict)
                                else log.metrics_json
                            ),
                            "adjustments_json": (
                                json.dumps(log.adjustments_json)
                                if isinstance(log.adjustments_json, dict)
                                else log.adjustments_json
                            ),
                            "match_score": log.match_score,
                            "phase": log.phase,
                            "weeks_remaining": log.weeks_remaining,
                        },
                    )
                else:
                    local_session.execute(
                        text(
                            """
                            INSERT INTO weekly_decision_log (
                                plan_id, week_num, week_start_date,
                                decision_type, trigger_reason,
                                metrics_json, adjustments_json,
                                match_score, phase, weeks_remaining
                            ) VALUES (
                                :plan_id, :week_num, :week_start_date,
                                :decision_type, :trigger_reason,
                                :metrics_json, :adjustments_json,
                                :match_score, :phase, :weeks_remaining
                            )
                        """
                        ),
                        {
                            "plan_id": local_plan_id,
                            "week_num": log.week_num,
                            "week_start_date": log.week_start_date,
                            "decision_type": log.decision_type,
                            "trigger_reason": log.trigger_reason,
                            "metrics_json": (
                                json.dumps(log.metrics_json)
                                if isinstance(log.metrics_json, dict)
                                else log.metrics_json
                            ),
                            "adjustments_json": (
                                json.dumps(log.adjustments_json)
                                if isinstance(log.adjustments_json, dict)
                                else log.adjustments_json
                            ),
                            "match_score": log.match_score,
                            "phase": log.phase,
                            "weeks_remaining": log.weeks_remaining,
                        },
                    )
                total_logs += 1

        local_session.commit()
        print(f"   ✅ Migrated {total_logs} weekly_decision_log entries")

    # Refresh materialized views
    print("\n10. Refreshing materialized views...")
    local_session.execute(text("REFRESH MATERIALIZED VIEW mv_athlete_metrics"))
    local_session.execute(text("REFRESH MATERIALIZED VIEW mv_longest_runs"))
    local_session.commit()
    print("   ✅ Refreshed materialized views")

    print("\n" + "=" * 60)
    print("✅ Migration complete!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  - Activities: {migrated_activities}")
    print(f"  - Splits: {total_splits}")
    print(f"  - Plans: {len(plans)}")
    print(f"  - Plan Workouts: {total_workouts if plan_id_map else 0}")
    print(f"  - Weekly Metrics: {total_metrics if plan_id_map else 0}")
    print(f"  - Weekly Decision Logs: {total_logs if plan_id_map else 0}")
    print(f"\nAll data mapped to athlete_id: {target_athlete_id}")

    prod_session.close()
    local_session.close()
    prod_engine.dispose()
    local_engine.dispose()

except Exception as e:
    print(f"\n❌ Error: {e}")
    traceback.print_exc()
    sys.exit(1)
