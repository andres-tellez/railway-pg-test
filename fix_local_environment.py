#!/usr/bin/env python3
"""
Fix Local Environment Script
============================

This script fixes common local environment issues for the SmartCoach application:
1. Creates missing database migrations (materialized view, run_score column)
2. Verifies database connection
3. Tests metrics endpoint
4. Provides diagnostic information

Usage:
    python fix_local_environment.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text, create_engine
import traceback

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


def load_environment():
    """Load environment variables for local development"""
    print("Loading environment variables...")

    # Try to load .env.local first
    env_local_path = Path(".env.local")
    if env_local_path.exists():
        load_dotenv(env_local_path, override=True)
        print(f"Loaded .env.local")
    else:
        print(".env.local not found, using system environment variables")

    return os.getenv("DATABASE_URL")


def test_database_connection(database_url):
    """Test database connection and basic functionality"""
    print(f"\n🔌 Testing database connection...")

    if not database_url:
        print("❌ DATABASE_URL not set")
        return False

    try:
        # Create engine and test connection
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()[0]
            print(
                f"✅ Database connection successful (test query returned: {test_value})"
            )
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def check_existing_schema(database_url):
    """Check if required database objects exist"""
    print(f"\n📊 Checking existing database schema...")

    engine = create_engine(database_url)
    with engine.connect() as conn:
        # Check if activities table exists
        try:
            result = conn.execute(text("SELECT COUNT(*) FROM activities LIMIT 1"))
            activities_count = result.fetchone()[0]
            print(f"✅ Activities table exists ({activities_count} records)")
        except Exception as e:
            print(f"❌ Activities table not found: {e}")
            return False

        # Check if run_score column exists
        try:
            result = conn.execute(text("SELECT run_score FROM activities LIMIT 1"))
            print("✅ run_score column exists")
        except Exception as e:
            print(f"⚠️  run_score column missing: {e}")

        # Check if materialized view exists
        try:
            result = conn.execute(
                text("SELECT COUNT(*) FROM mv_athlete_metrics LIMIT 1")
            )
            metrics_count = result.fetchone()[0]
            print(f"✅ mv_athlete_metrics view exists ({metrics_count} records)")
        except Exception as e:
            print(f"⚠️  mv_athlete_metrics view missing: {e}")

        return True


def run_database_migrations(database_url):
    """Run database migrations to create missing objects"""
    print(f"\n🚀 Running database migrations...")

    engine = create_engine(database_url)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Migration 1: Add run_score column
            print("📝 Adding run_score column...")
            try:
                conn.execute(
                    text(
                        """
                    ALTER TABLE activities
                    ADD COLUMN run_score DECIMAL(10,2) GENERATED ALWAYS AS (
                        CASE
                            WHEN type = 'Run'
                                 AND distance >= 2.0
                                 AND moving_time >= 720
                                 AND moving_time > 0
                                 AND distance > 0 THEN
                                (distance * 1609.34 * (1609.34 / (moving_time / distance))) *
                                COALESCE(average_heartrate / NULLIF(max_heartrate, 0), 1.0)
                            ELSE NULL
                        END
                    ) STORED;
                """
                    )
                )
                print("✅ run_score column added")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print("✅ run_score column already exists")
                else:
                    print(f"⚠️  run_score column creation failed: {e}")

            # Migration 2: Create materialized view
            print("📝 Creating mv_athlete_metrics materialized view...")
            try:
                # Drop existing view if it exists
                conn.execute(
                    text("DROP MATERIALIZED VIEW IF EXISTS mv_athlete_metrics CASCADE;")
                )

                # Create the materialized view
                with open("database_migrations/002_create_metrics_view.sql", "r") as f:
                    view_sql = f.read()

                conn.execute(text(view_sql))
                print("✅ mv_athlete_metrics materialized view created")

                # Create indexes
                conn.execute(
                    text(
                        """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_athlete_metrics_athlete_id
                    ON mv_athlete_metrics(athlete_id);
                """
                    )
                )
                print("✅ Indexes created")

            except Exception as e:
                print(f"❌ Materialized view creation failed: {e}")
                raise

            trans.commit()
            print("✅ All migrations completed successfully")

        except Exception as e:
            trans.rollback()
            print(f"❌ Migration failed, rolled back: {e}")
            raise


def refresh_materialized_view(database_url):
    """Refresh the materialized view with current data"""
    print(f"\n🔄 Refreshing materialized view...")

    engine = create_engine(database_url)
    with engine.connect() as conn:
        try:
            conn.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_athlete_metrics;")
            )
            conn.commit()
            print("✅ Materialized view refreshed")
        except Exception as e:
            print(f"⚠️  Materialized view refresh failed: {e}")


def test_metrics_functionality(database_url):
    """Test the metrics functionality"""
    print(f"\n🧪 Testing metrics functionality...")

    engine = create_engine(database_url)
    with engine.connect() as conn:
        # Test materialized view query
        try:
            result = conn.execute(
                text(
                    """
                SELECT athlete_id, current_distance, current_runs,
                       distance_change_pct, runs_change_pct,
                       zone_1_pct, zone_2_pct, zone_3_pct, zone_4_pct, zone_5_pct
                FROM mv_athlete_metrics
                LIMIT 5;
            """
                )
            )

            rows = result.fetchall()
            if rows:
                print(f"✅ Materialized view query successful ({len(rows)} records)")
                for row in rows:
                    print(
                        f"   Athlete {row.athlete_id}: {row.current_distance:.1f} mi, {row.current_runs} runs"
                    )
            else:
                print("⚠️  Materialized view is empty (no athlete data)")

        except Exception as e:
            print(f"❌ Materialized view query failed: {e}")

        # Test run_score calculation
        try:
            result = conn.execute(
                text(
                    """
                SELECT activity_id, run_score, distance, moving_time, average_heartrate, max_heartrate
                FROM activities
                WHERE run_score IS NOT NULL
                LIMIT 5;
            """
                )
            )

            rows = result.fetchall()
            if rows:
                print(
                    f"✅ run_score calculation working ({len(rows)} activities with scores)"
                )
                for row in rows:
                    print(f"   Activity {row.activity_id}: score={row.run_score:.2f}")
            else:
                print("⚠️  No activities have run_score calculated")

        except Exception as e:
            print(f"❌ run_score query failed: {e}")


def main():
    """Main function to fix local environment"""
    print("SmartCoach Local Environment Fix Script")
    print("=" * 50)

    # Load environment
    database_url = load_environment()

    # Test database connection
    if not test_database_connection(database_url):
        print("\n❌ Cannot proceed without database connection")
        sys.exit(1)

    # Check existing schema
    if not check_existing_schema(database_url):
        print("\n❌ Cannot proceed without activities table")
        sys.exit(1)

    # Run migrations
    try:
        run_database_migrations(database_url)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    # Refresh materialized view
    refresh_materialized_view(database_url)

    # Test functionality
    test_metrics_functionality(database_url)

    print("\n🎉 Local environment fix completed!")
    print("\nNext steps:")
    print("1. Start your backend server: python run.py")
    print("2. Start your frontend server: cd frontend && npm run dev")
    print("3. Test the metrics page in your browser")
    print("4. If issues persist, check the logs for specific error messages")


if __name__ == "__main__":
    main()
