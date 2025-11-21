#!/usr/bin/env python3
"""
Migrate Production Strava Data to Local Environment

This script copies data from production (main Strava account) to local
(test Strava account) and updates all IDs to work with the local environment.

Usage:
    python scripts/migrate_prod_to_local.py

Requirements:
    - Production DATABASE_URL in environment or .env.prod
    - Local DATABASE_URL in .env.local
    - Both databases accessible
"""

import os
import sys
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import traceback

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


class DataMigrator:
    """Handles migration of data from production to local with ID remapping."""

    def __init__(self, prod_db_url: str, local_db_url: str):
        self.prod_engine = create_engine(prod_db_url, echo=False)
        self.local_engine = create_engine(local_db_url, echo=False)
        self.prod_session = sessionmaker(bind=self.prod_engine)()
        self.local_session = sessionmaker(bind=self.local_engine)()

        # ID mappings
        self.user_id_map: Dict[str, str] = {}  # prod_user_id -> local_user_id
        self.athlete_id_map: Dict[int, int] = {}  # prod_athlete_id -> local_athlete_id
        self.plan_id_map: Dict[int, int] = {}  # prod_plan_id -> local_plan_id
        self.conversation_id_map: Dict[str, str] = {}  # prod_conv_id -> local_conv_id

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.prod_session.close()
        self.local_session.close()
        self.prod_engine.dispose()
        self.local_engine.dispose()

    def get_prod_user_and_athlete(self) -> Optional[Tuple[str, int]]:
        """Get the production user_id and athlete_id (main account)."""
        try:
            result = self.prod_session.execute(
                text(
                    """
                    SELECT ua.user_id, ua.athlete_id
                    FROM user_athletes ua
                    ORDER BY ua.created_at DESC
                    LIMIT 1
                """
                )
            ).fetchone()
            if result:
                return (str(result[0]), int(result[1]))
            return None
        except Exception as e:
            print(f"❌ Error getting prod user/athlete: {e}")
            return None

    def get_local_user_and_athlete(self) -> Optional[Tuple[str, int]]:
        """Get the local user_id and athlete_id (test account)."""
        try:
            result = self.local_session.execute(
                text(
                    """
                    SELECT ua.user_id, ua.athlete_id
                    FROM user_athletes ua
                    ORDER BY ua.created_at DESC
                    LIMIT 1
                """
                )
            ).fetchone()
            if result:
                return (str(result[0]), int(result[1]))
            return None
        except Exception as e:
            print(f"❌ Error getting local user/athlete: {e}")
            return None

    def migrate_user_identity(self):
        """Copy user_identity and create mapping."""
        print("\n📋 Migrating user_identity...")
        try:
            # Get prod user
            prod_user_id, _ = self.get_prod_user_and_athlete()
            if not prod_user_id:
                print("❌ No production user found")
                return False

            # Get local user
            local_user_id, _ = self.get_local_user_and_athlete()
            if not local_user_id:
                print(
                    "❌ No local user found. Please ensure test account is connected."
                )
                return False

            # Get prod user data
            prod_user = self.prod_session.execute(
                text("SELECT * FROM user_identity WHERE user_id = :user_id"),
                {"user_id": prod_user_id},
            ).fetchone()

            if not prod_user:
                print("❌ Production user not found in user_identity")
                return False

            # Check if local user exists, if not create it
            local_user = self.local_session.execute(
                text("SELECT * FROM user_identity WHERE user_id = :user_id"),
                {"user_id": local_user_id},
            ).fetchone()

            if not local_user:
                # Copy user data but use local user_id
                self.local_session.execute(
                    text(
                        """
                        INSERT INTO user_identity (user_id, email, email_verified, name, picture, updated_at)
                        VALUES (:user_id, :email, :email_verified, :name, :picture, :updated_at)
                    """
                    ),
                    {
                        "user_id": local_user_id,
                        "email": prod_user.email,
                        "email_verified": prod_user.email_verified,
                        "name": prod_user.name,
                        "picture": prod_user.picture,
                        "updated_at": prod_user.updated_at,
                    },
                )
                self.local_session.commit()
                print(f"✅ Created user_identity: {local_user_id}")

            self.user_id_map[prod_user_id] = local_user_id
            print(f"✅ Mapped user_id: {prod_user_id} -> {local_user_id}")
            return True

        except Exception as e:
            print(f"❌ Error migrating user_identity: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_user_athletes(self):
        """Copy user_athletes and create athlete_id mapping."""
        print("\n📋 Migrating user_athletes...")
        try:
            prod_user_id, prod_athlete_id = self.get_prod_user_and_athlete()
            local_user_id, local_athlete_id = self.get_local_user_and_athlete()

            if not all(
                [prod_user_id, prod_athlete_id, local_user_id, local_athlete_id]
            ):
                print("❌ Missing user/athlete IDs")
                return False

            # Get prod athlete link
            prod_link = self.prod_session.execute(
                text("SELECT * FROM user_athletes WHERE athlete_id = :athlete_id"),
                {"athlete_id": prod_athlete_id},
            ).fetchone()

            if not prod_link:
                print("❌ Production athlete link not found")
                return False

            # Check if local link exists
            local_link = self.local_session.execute(
                text("SELECT * FROM user_athletes WHERE athlete_id = :athlete_id"),
                {"athlete_id": local_athlete_id},
            ).fetchone()

            if not local_link:
                # Create local link
                self.local_session.execute(
                    text(
                        """
                        INSERT INTO user_athletes (user_id, athlete_id, created_at)
                        VALUES (:user_id, :athlete_id, :created_at)
                    """
                    ),
                    {
                        "user_id": local_user_id,
                        "athlete_id": local_athlete_id,
                        "created_at": prod_link.created_at,
                    },
                )
                self.local_session.commit()
                print(f"✅ Created user_athletes link: {local_athlete_id}")

            self.athlete_id_map[prod_athlete_id] = local_athlete_id
            print(f"✅ Mapped athlete_id: {prod_athlete_id} -> {local_athlete_id}")
            return True

        except Exception as e:
            print(f"❌ Error migrating user_athletes: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_user_profile(self):
        """Copy user_profile with user_id mapping."""
        print("\n📋 Migrating user_profile...")
        try:
            prod_user_id = list(self.user_id_map.keys())[0]
            local_user_id = self.user_id_map[prod_user_id]

            prod_profile = self.prod_session.execute(
                text("SELECT * FROM user_profile WHERE user_id = :user_id"),
                {"user_id": prod_user_id},
            ).fetchone()

            if not prod_profile:
                print("⚠️  No user_profile found in production (skipping)")
                return True

            # Check if local profile exists
            local_profile = self.local_session.execute(
                text("SELECT * FROM user_profile WHERE user_id = :user_id"),
                {"user_id": local_user_id},
            ).fetchone()

            if local_profile:
                # Update existing (removed motivation and training_days columns, added max_hr)
                self.local_session.execute(
                    text(
                        """
                        UPDATE user_profile
                        SET age_group = :age_group, height_feet = :height_feet,
                            height_inches = :height_inches, weight = :weight,
                            max_hr = :max_hr
                        WHERE user_id = :user_id
                    """
                    ),
                    {
                        "user_id": local_user_id,
                        "age_group": prod_profile.age_group,
                        "height_feet": prod_profile.height_feet,
                        "height_inches": prod_profile.height_inches,
                        "weight": prod_profile.weight,
                        "max_hr": getattr(
                            prod_profile, "max_hr", None
                        ),  # Safely get max_hr if it exists
                    },
                )
            else:
                # Insert new (removed motivation and training_days columns, added max_hr)
                self.local_session.execute(
                    text(
                        """
                        INSERT INTO user_profile (user_id, age_group, height_feet, height_inches, weight, max_hr)
                        VALUES (:user_id, :age_group, :height_feet, :height_inches, :weight, :max_hr)
                    """
                    ),
                    {
                        "user_id": local_user_id,
                        "age_group": prod_profile.age_group,
                        "height_feet": prod_profile.height_feet,
                        "height_inches": prod_profile.height_inches,
                        "weight": prod_profile.weight,
                        "max_hr": getattr(
                            prod_profile, "max_hr", None
                        ),  # Safely get max_hr if it exists
                    },
                )

            self.local_session.commit()
            print(f"✅ Migrated user_profile")
            return True

        except Exception as e:
            print(f"❌ Error migrating user_profile: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_activities(self):
        """Copy activities with athlete_id and user_id mapping."""
        print("\n📋 Migrating activities...")
        try:
            prod_user_id = list(self.user_id_map.keys())[0]
            local_user_id = self.user_id_map[prod_user_id]
            prod_athlete_id = list(self.athlete_id_map.keys())[0]
            local_athlete_id = self.athlete_id_map[prod_athlete_id]

            # Get all prod activities
            prod_activities = self.prod_session.execute(
                text("SELECT * FROM activities WHERE user_id = :user_id"),
                {"user_id": prod_user_id},
            ).fetchall()

            if not prod_activities:
                print("⚠️  No activities found in production")
                return True

            print(f"   Found {len(prod_activities)} activities to migrate")

            migrated_count = 0
            for activity in prod_activities:
                # Check if activity already exists (by activity_id - Strava ID)
                existing = self.local_session.execute(
                    text(
                        "SELECT activity_id FROM activities WHERE activity_id = :activity_id"
                    ),
                    {"activity_id": activity.activity_id},
                ).fetchone()

                if existing:
                    # Update existing
                    self.local_session.execute(
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
                            "athlete_id": local_athlete_id,
                            "user_id": local_user_id,
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
                    # Insert new
                    self.local_session.execute(
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
                            "athlete_id": local_athlete_id,
                            "user_id": local_user_id,
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
                migrated_count += 1

            self.local_session.commit()
            print(f"✅ Migrated {migrated_count} activities")
            return True

        except Exception as e:
            print(f"❌ Error migrating activities: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_splits(self):
        """Copy splits (activity_id stays the same - it's Strava's ID)."""
        print("\n📋 Migrating splits...")
        try:
            prod_user_id = list(self.user_id_map.keys())[0]

            # Get activity_ids for this user
            activity_ids = self.prod_session.execute(
                text("SELECT activity_id FROM activities WHERE user_id = :user_id"),
                {"user_id": prod_user_id},
            ).fetchall()

            if not activity_ids:
                print("⚠️  No activities found, skipping splits")
                return True

            activity_id_list = [row[0] for row in activity_ids]
            total_splits = 0

            for activity_id in activity_id_list:
                prod_splits = self.prod_session.execute(
                    text("SELECT * FROM splits WHERE activity_id = :activity_id"),
                    {"activity_id": activity_id},
                ).fetchall()

                for split in prod_splits:
                    # Check if split exists
                    existing = self.local_session.execute(
                        text(
                            """
                            SELECT id FROM splits
                            WHERE activity_id = :activity_id AND lap_index = :lap_index
                        """
                        ),
                        {
                            "activity_id": split.activity_id,
                            "lap_index": split.lap_index,
                        },
                    ).fetchone()

                    if existing:
                        # Update existing
                        self.local_session.execute(
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
                        # Insert new
                        self.local_session.execute(
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

            self.local_session.commit()
            print(f"✅ Migrated {total_splits} splits")
            return True

        except Exception as e:
            print(f"❌ Error migrating splits: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_plans(self):
        """Copy plans with user_id mapping and create plan_id mapping."""
        print("\n📋 Migrating plans...")
        try:
            prod_user_id = list(self.user_id_map.keys())[0]
            local_user_id = self.user_id_map[prod_user_id]

            prod_plans = self.prod_session.execute(
                text("SELECT * FROM plans WHERE user_id = :user_id"),
                {"user_id": prod_user_id},
            ).fetchall()

            if not prod_plans:
                print("⚠️  No plans found in production")
                return True

            print(f"   Found {len(prod_plans)} plans to migrate")

            for plan in prod_plans:
                # Insert new plan (will get new plan_id)
                result = self.local_session.execute(
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
                        "user_id": local_user_id,
                        "plan_name": plan.plan_name,
                        "race_date": plan.race_date,
                        "race_distance": plan.race_distance,
                        "race_name": plan.race_name,
                        "race_location": plan.race_location,
                        "race_metadata": plan.race_metadata,
                        "primary_goal": plan.primary_goal,
                        "target_time": plan.target_time,
                        "training_days": plan.training_days,
                        "notes": plan.notes,
                        "is_active": plan.is_active,
                        "created_by": plan.created_by,
                        "created_at": plan.created_at,
                    },
                )
                new_plan_id = result.fetchone()[0]
                self.plan_id_map[plan.id] = new_plan_id
                print(f"   Mapped plan_id: {plan.id} -> {new_plan_id}")

            self.local_session.commit()
            print(f"✅ Migrated {len(prod_plans)} plans")
            return True

        except Exception as e:
            print(f"❌ Error migrating plans: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_plan_workouts(self):
        """Copy plan_workouts with plan_id mapping."""
        print("\n📋 Migrating plan_workouts...")
        try:
            if not self.plan_id_map:
                print("⚠️  No plans migrated, skipping plan_workouts")
                return True

            total_workouts = 0
            for prod_plan_id, local_plan_id in self.plan_id_map.items():
                prod_workouts = self.prod_session.execute(
                    text("SELECT * FROM plan_workouts WHERE plan_id = :plan_id"),
                    {"plan_id": prod_plan_id},
                ).fetchall()

                for workout in prod_workouts:
                    # Check if workout exists
                    existing = self.local_session.execute(
                        text(
                            """
                            SELECT id FROM plan_workouts
                            WHERE plan_id = :plan_id AND date = :date
                        """
                        ),
                        {"plan_id": local_plan_id, "date": workout.date},
                    ).fetchone()

                    if existing:
                        # Update existing
                        self.local_session.execute(
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
                                "segments": workout.segments,
                                "run_type_key": workout.run_type_key,
                                "phase": workout.phase,
                                "pace_ranges": workout.pace_ranges,
                                "allow_quality": workout.allow_quality,
                                "cues": workout.cues,
                                "quality_insert": workout.quality_insert,
                            },
                        )
                    else:
                        # Insert new
                        self.local_session.execute(
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
                                "segments": workout.segments,
                                "run_type_key": workout.run_type_key,
                                "phase": workout.phase,
                                "pace_ranges": workout.pace_ranges,
                                "allow_quality": workout.allow_quality,
                                "cues": workout.cues,
                                "quality_insert": workout.quality_insert,
                            },
                        )
                    total_workouts += 1

            self.local_session.commit()
            print(f"✅ Migrated {total_workouts} plan_workouts")
            return True

        except Exception as e:
            print(f"❌ Error migrating plan_workouts: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_weekly_metrics(self):
        """Copy weekly_metrics with plan_id mapping."""
        print("\n📋 Migrating weekly_metrics...")
        try:
            if not self.plan_id_map:
                print("⚠️  No plans migrated, skipping weekly_metrics")
                return True

            total_metrics = 0
            for prod_plan_id, local_plan_id in self.plan_id_map.items():
                prod_metrics = self.prod_session.execute(
                    text("SELECT * FROM weekly_metrics WHERE plan_id = :plan_id"),
                    {"plan_id": prod_plan_id},
                ).fetchall()

                for metric in prod_metrics:
                    # Check if metric exists
                    existing = self.local_session.execute(
                        text(
                            """
                            SELECT id FROM weekly_metrics
                            WHERE plan_id = :plan_id AND week_num = :week_num
                        """
                        ),
                        {"plan_id": local_plan_id, "week_num": metric.week_num},
                    ).fetchone()

                    if existing:
                        # Update existing
                        self.local_session.execute(
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
                                "context_score": metric.context_score,
                                "phase": metric.phase,
                                "weeks_remaining": metric.weeks_remaining,
                            },
                        )
                    else:
                        # Insert new
                        self.local_session.execute(
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
                                "context_score": metric.context_score,
                                "phase": metric.phase,
                                "weeks_remaining": metric.weeks_remaining,
                            },
                        )
                    total_metrics += 1

            self.local_session.commit()
            print(f"✅ Migrated {total_metrics} weekly_metrics")
            return True

        except Exception as e:
            print(f"❌ Error migrating weekly_metrics: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_weekly_decision_log(self):
        """Copy weekly_decision_log with plan_id mapping."""
        print("\n📋 Migrating weekly_decision_log...")
        try:
            if not self.plan_id_map:
                print("⚠️  No plans migrated, skipping weekly_decision_log")
                return True

            total_logs = 0
            for prod_plan_id, local_plan_id in self.plan_id_map.items():
                prod_logs = self.prod_session.execute(
                    text("SELECT * FROM weekly_decision_log WHERE plan_id = :plan_id"),
                    {"plan_id": prod_plan_id},
                ).fetchall()

                for log in prod_logs:
                    # Check if log exists
                    existing = self.local_session.execute(
                        text(
                            """
                            SELECT id FROM weekly_decision_log
                            WHERE plan_id = :plan_id AND week_num = :week_num
                        """
                        ),
                        {"plan_id": local_plan_id, "week_num": log.week_num},
                    ).fetchone()

                    if existing:
                        # Update existing
                        self.local_session.execute(
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
                                "metrics_json": log.metrics_json,
                                "adjustments_json": log.adjustments_json,
                                "match_score": log.match_score,
                                "phase": log.phase,
                                "weeks_remaining": log.weeks_remaining,
                            },
                        )
                    else:
                        # Insert new
                        self.local_session.execute(
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
                                "metrics_json": log.metrics_json,
                                "adjustments_json": log.adjustments_json,
                                "match_score": log.match_score,
                                "phase": log.phase,
                                "weeks_remaining": log.weeks_remaining,
                            },
                        )
                    total_logs += 1

            self.local_session.commit()
            print(f"✅ Migrated {total_logs} weekly_decision_log entries")
            return True

        except Exception as e:
            print(f"❌ Error migrating weekly_decision_log: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_conversations(self):
        """Copy conversations and messages with user_id mapping."""
        print("\n📋 Migrating conversations...")
        try:
            prod_user_id = list(self.user_id_map.keys())[0]
            local_user_id = self.user_id_map[prod_user_id]

            prod_conversations = self.prod_session.execute(
                text("SELECT * FROM conversations WHERE user_id = :user_id"),
                {"user_id": prod_user_id},
            ).fetchall()

            if not prod_conversations:
                print("⚠️  No conversations found in production")
                return True

            print(f"   Found {len(prod_conversations)} conversations to migrate")

            for conv in prod_conversations:
                # Create new conversation with new UUID
                new_conv_id = str(uuid.uuid4())
                self.local_session.execute(
                    text(
                        """
                        INSERT INTO conversations (id, user_id, title, is_active, created_at, updated_at)
                        VALUES (:id, :user_id, :title, :is_active, :created_at, :updated_at)
                    """
                    ),
                    {
                        "id": new_conv_id,
                        "user_id": local_user_id,
                        "title": conv.title,
                        "is_active": conv.is_active,
                        "created_at": conv.created_at,
                        "updated_at": conv.updated_at,
                    },
                )
                self.conversation_id_map[str(conv.id)] = new_conv_id

                # Migrate messages
                prod_messages = self.prod_session.execute(
                    text(
                        "SELECT * FROM conversation_messages WHERE conversation_id = :conv_id"
                    ),
                    {"conv_id": str(conv.id)},
                ).fetchall()

                for msg in prod_messages:
                    self.local_session.execute(
                        text(
                            """
                            INSERT INTO conversation_messages (id, conversation_id, role, content, created_at)
                            VALUES (:id, :conversation_id, :role, :content, :created_at)
                        """
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "conversation_id": new_conv_id,
                            "role": msg.role,
                            "content": msg.content,
                            "created_at": msg.created_at,
                        },
                    )

            self.local_session.commit()
            print(f"✅ Migrated {len(prod_conversations)} conversations")
            return True

        except Exception as e:
            print(f"❌ Error migrating conversations: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def migrate_strava_sync_status(self):
        """Copy strava_sync_status with user_id and athlete_id mapping."""
        print("\n📋 Migrating strava_sync_status...")
        try:
            prod_user_id = list(self.user_id_map.keys())[0]
            local_user_id = self.user_id_map[prod_user_id]
            prod_athlete_id = list(self.athlete_id_map.keys())[0]
            local_athlete_id = self.athlete_id_map[prod_athlete_id]

            prod_sync_status = self.prod_session.execute(
                text("SELECT * FROM strava_sync_status WHERE user_id = :user_id"),
                {"user_id": prod_user_id},
            ).fetchall()

            if not prod_sync_status:
                print("⚠️  No strava_sync_status found in production")
                return True

            print(f"   Found {len(prod_sync_status)} sync status records to migrate")

            for status in prod_sync_status:
                # Check if status exists
                existing = self.local_session.execute(
                    text(
                        """
                        SELECT id FROM strava_sync_status
                        WHERE user_id = :user_id AND athlete_id = :athlete_id
                    """
                    ),
                    {"user_id": local_user_id, "athlete_id": local_athlete_id},
                ).fetchone()

                if existing:
                    # Update existing
                    self.local_session.execute(
                        text(
                            """
                            UPDATE strava_sync_status
                            SET status = :status, progress = :progress,
                                step = :step, detail = :detail,
                                error_code = :error_code, started_at = :started_at,
                                updated_at = :updated_at, completed_at = :completed_at
                            WHERE user_id = :user_id AND athlete_id = :athlete_id
                        """
                        ),
                        {
                            "user_id": local_user_id,
                            "athlete_id": local_athlete_id,
                            "status": status.status,
                            "progress": status.progress,
                            "step": status.step,
                            "detail": status.detail,
                            "error_code": status.error_code,
                            "started_at": status.started_at,
                            "updated_at": status.updated_at,
                            "completed_at": status.completed_at,
                        },
                    )
                else:
                    # Insert new
                    self.local_session.execute(
                        text(
                            """
                            INSERT INTO strava_sync_status (
                                user_id, athlete_id, status, progress,
                                step, detail, error_code, started_at,
                                updated_at, completed_at
                            ) VALUES (
                                :user_id, :athlete_id, :status, :progress,
                                :step, :detail, :error_code, :started_at,
                                :updated_at, :completed_at
                            )
                        """
                        ),
                        {
                            "user_id": local_user_id,
                            "athlete_id": local_athlete_id,
                            "status": status.status,
                            "progress": status.progress,
                            "step": status.step,
                            "detail": status.detail,
                            "error_code": status.error_code,
                            "started_at": status.started_at,
                            "updated_at": status.updated_at,
                            "completed_at": status.completed_at,
                        },
                    )

            self.local_session.commit()
            print(f"✅ Migrated {len(prod_sync_status)} strava_sync_status records")
            return True

        except Exception as e:
            print(f"❌ Error migrating strava_sync_status: {e}")
            traceback.print_exc()
            self.local_session.rollback()
            return False

    def run_migration(self):
        """Run the complete migration process."""
        print("=" * 60)
        print("🚀 Production to Local Data Migration")
        print("=" * 60)

        steps = [
            ("user_identity", self.migrate_user_identity),
            ("user_athletes", self.migrate_user_athletes),
            ("user_profile", self.migrate_user_profile),
            ("activities", self.migrate_activities),
            ("splits", self.migrate_splits),
            ("plans", self.migrate_plans),
            ("plan_workouts", self.migrate_plan_workouts),
            ("weekly_metrics", self.migrate_weekly_metrics),
            ("weekly_decision_log", self.migrate_weekly_decision_log),
            ("strava_sync_status", self.migrate_strava_sync_status),
            ("conversations", self.migrate_conversations),
        ]

        success_count = 0
        for step_name, step_func in steps:
            if step_func():
                success_count += 1
            else:
                print(f"\n⚠️  Migration stopped at {step_name}")
                break

        print("\n" + "=" * 60)
        if success_count == len(steps):
            print("✅ Migration completed successfully!")
            print("\n⚠️  IMPORTANT NOTES:")
            print("   - Tokens were NOT migrated (they won't work with test account)")
            print(
                "   - You may need to re-authenticate with Strava in local environment"
            )
            print("   - Activity IDs remain the same (Strava's global IDs)")
            print("   - Plans maintain their is_active status from production")
            print("   - Sync status migrated for UX consistency")
        else:
            print(f"⚠️  Migration completed with {len(steps) - success_count} errors")
        print("=" * 60)


def main():
    """Main entry point."""
    # Load environment variables
    env_local = Path(".env.local")
    env_prod = Path(".env.prod")

    if env_local.exists():
        load_dotenv(env_local, override=False)
        print(f"✅ Loaded .env.local")

    if env_prod.exists():
        load_dotenv(env_prod, override=False)
        print(f"✅ Loaded .env.prod")

    # Get database URLs
    prod_db_url = os.getenv("PROD_DATABASE_URL") or os.getenv("DATABASE_URL")
    local_db_url = os.getenv("DATABASE_URL")

    if not prod_db_url:
        print("❌ PROD_DATABASE_URL or DATABASE_URL not set")
        print("   Set PROD_DATABASE_URL for production database")
        print("   Set DATABASE_URL for local database")
        return 1

    if not local_db_url:
        print("❌ DATABASE_URL not set (local database)")
        return 1

    # If DATABASE_URL is set but PROD_DATABASE_URL is not, assume current DATABASE_URL is prod
    if not os.getenv("PROD_DATABASE_URL") and os.getenv("DATABASE_URL"):
        print("⚠️  PROD_DATABASE_URL not set, assuming DATABASE_URL is production")
        print("   Please set PROD_DATABASE_URL explicitly for production")
        response = input("   Continue anyway? (yes/no): ")
        if response.lower() != "yes":
            return 1
        prod_db_url = os.getenv("DATABASE_URL")
        # For local, you'll need to set it separately
        print("   Please set DATABASE_URL to your local database URL")
        local_db_url = input("   Local DATABASE_URL: ").strip()
        if not local_db_url:
            print("❌ Local DATABASE_URL required")
            return 1

    print(f"\n📊 Production DB: {prod_db_url[:50]}...")
    print(f"📊 Local DB: {local_db_url[:50]}...")

    # Confirm before proceeding
    print("\n⚠️  This will copy data from production to local and update IDs")
    response = input("Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled.")
        return 0

    # Run migration
    try:
        with DataMigrator(prod_db_url, local_db_url) as migrator:
            migrator.run_migration()
        return 0
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
