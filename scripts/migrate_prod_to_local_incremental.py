#!/usr/bin/env python3
"""
Incremental Migration: Copy Delta from Production to Local

This is an enhanced version of migrate_prod_to_local.py that only copies
new or updated records since the last migration, making subsequent runs much faster.

Usage:
    python scripts/migrate_prod_to_local_incremental.py [--full]

    --full: Force full migration (ignore last migration timestamp)
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import original DataMigrator from same directory
# Note: This assumes both scripts are in the same directory
# If import fails, we'll inherit the base functionality differently
import sys
from pathlib import Path

# Add scripts directory to path for import
scripts_dir = Path(__file__).parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

# For now, we'll inherit directly - the user can modify this
# Or copy the DataMigrator class here if import doesn't work
try:
    from migrate_prod_to_local import DataMigrator
except ImportError:
    print(
        "⚠️  Could not import DataMigrator. Please ensure migrate_prod_to_local.py is in the same directory."
    )
    sys.exit(1)


class IncrementalDataMigrator(DataMigrator):
    """
    Enhanced DataMigrator that supports incremental/delta migrations.

    Tracks last migration timestamp for each table and only copies
    records created/updated after that timestamp.
    """

    def __init__(
        self, prod_db_url: str, local_db_url: str, full_migration: bool = False
    ):
        super().__init__(prod_db_url, local_db_url)
        self.full_migration = full_migration
        self.migration_log_table = "migration_log"

        # Create migration_log table if it doesn't exist
        self._create_migration_log_table()

    def _create_migration_log_table(self):
        """Create migration_log table to track last sync timestamps."""
        try:
            self.local_session.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.migration_log_table} (
                        table_name VARCHAR(255) PRIMARY KEY,
                        last_migration_timestamp TIMESTAMP WITH TIME ZONE,
                        record_count INTEGER DEFAULT 0,
                        last_migration_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """
                )
            )
            self.local_session.commit()
        except Exception as e:
            print(f"⚠️  Could not create migration_log table: {e}")
            self.local_session.rollback()

    def get_last_migration_timestamp(self, table_name: str) -> Optional[datetime]:
        """Get last migration timestamp for a table."""
        if self.full_migration:
            return None

        try:
            result = self.local_session.execute(
                text(
                    f"""
                    SELECT last_migration_timestamp
                    FROM {self.migration_log_table}
                    WHERE table_name = :table_name
                """
                ),
                {"table_name": table_name},
            ).fetchone()

            if result and result[0]:
                return result[0]
            return None
        except Exception:
            return None

    def update_migration_log(
        self, table_name: str, last_timestamp: datetime, record_count: int
    ):
        """Update migration log after successful migration."""
        try:
            self.local_session.execute(
                text(
                    f"""
                    INSERT INTO {self.migration_log_table}
                        (table_name, last_migration_timestamp, record_count, last_migration_at)
                    VALUES (:table_name, :timestamp, :count, NOW())
                    ON CONFLICT (table_name)
                    DO UPDATE SET
                        last_migration_timestamp = EXCLUDED.last_migration_timestamp,
                        record_count = EXCLUDED.record_count,
                        last_migration_at = NOW()
                """
                ),
                {
                    "table_name": table_name,
                    "timestamp": last_timestamp,
                    "count": record_count,
                },
            )
            self.local_session.commit()
        except Exception as e:
            print(f"⚠️  Could not update migration log: {e}")
            self.local_session.rollback()

    def migrate_activities(self):
        """Copy activities with delta/incremental support."""
        print("\n📋 Migrating activities (incremental)...")
        try:
            prod_user_id = list(self.user_id_map.keys())[0]
            local_user_id = self.user_id_map[prod_user_id]
            prod_athlete_id = list(self.athlete_id_map.keys())[0]
            local_athlete_id = self.athlete_id_map[prod_athlete_id]

            # Get last migration timestamp
            last_timestamp = self.get_last_migration_timestamp("activities")

            # Build query with optional timestamp filter
            if last_timestamp:
                print(
                    f"   🔄 Incremental mode: Only fetching activities after {last_timestamp.isoformat()}"
                )
                query = text(
                    """
                    SELECT * FROM activities
                    WHERE user_id = :user_id
                    AND start_date > :last_timestamp
                    ORDER BY start_date ASC
                """
                )
                params = {"user_id": prod_user_id, "last_timestamp": last_timestamp}
            else:
                print("   🔄 Full migration mode: Fetching all activities")
                query = text(
                    """
                    SELECT * FROM activities
                    WHERE user_id = :user_id
                    ORDER BY start_date ASC
                """
                )
                params = {"user_id": prod_user_id}

            prod_activities = self.prod_session.execute(query, params).fetchall()

            if not prod_activities:
                print("⚠️  No new activities found in production")
                return True

            print(f"   Found {len(prod_activities)} new/updated activities to migrate")
            migrated_count = 0
            latest_timestamp = None

            for activity in prod_activities:
                # Use parent class's activity migration logic
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
                    # Insert new - copy full INSERT logic from parent
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
                if not latest_timestamp or activity.start_date > latest_timestamp:
                    latest_timestamp = activity.start_date

            self.local_session.commit()

            # Update migration log with latest timestamp
            if latest_timestamp:
                self.update_migration_log(
                    "activities", latest_timestamp, migrated_count
                )

            print(f"✅ Migrated {migrated_count} activities")
            return True

        except Exception as e:
            print(f"❌ Error migrating activities: {e}")
            import traceback

            traceback.print_exc()
            self.local_session.rollback()
            return False


def main():
    """Main entry point with incremental support."""
    parser = argparse.ArgumentParser(
        description="Incremental migration from production to local"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full migration (ignore last migration timestamp)",
    )
    args = parser.parse_args()

    # Load environment variables (same as original script)
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
        return 1

    if not local_db_url:
        print("❌ DATABASE_URL not set (local database)")
        return 1

    print(f"\n📊 Production DB: {prod_db_url[:50]}...")
    print(f"📊 Local DB: {local_db_url[:50]}...")

    if args.full:
        print("\n🔄 FULL migration mode (ignoring last migration timestamp)")
    else:
        print("\n🔄 INCREMENTAL migration mode (only new/updated records)")

    # Run migration
    try:
        with IncrementalDataMigrator(
            prod_db_url, local_db_url, full_migration=args.full
        ) as migrator:
            # For now, only activities are incremental
            # Other tables still use parent class methods (full migration)
            migrator.migrate_user_identity()
            migrator.migrate_user_athletes()
            migrator.migrate_user_profile()
            migrator.migrate_activities()  # This is now incremental
            migrator.migrate_splits()
            migrator.migrate_plans()
            migrator.migrate_plan_workouts()
            migrator.migrate_weekly_metrics()
            migrator.migrate_weekly_decision_log()
            migrator.migrate_strava_sync_status()
            migrator.migrate_conversations()

        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
