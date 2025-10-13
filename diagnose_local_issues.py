#!/usr/bin/env python3
"""
Simple Local Environment Diagnostic Script
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


def main():
    print("SmartCoach Local Environment Diagnostic")
    print("=" * 40)

    # Check environment files
    print("\n1. Checking environment files...")
    env_files = [".env.local", ".env.staging", ".env.prod"]
    for env_file in env_files:
        if Path(env_file).exists():
            print(f"   Found: {env_file}")
        else:
            print(f"   Missing: {env_file}")

    # Load environment
    env_local_path = Path(".env.local")
    if env_local_path.exists():
        load_dotenv(env_local_path, override=True)
        print("   Loaded .env.local")

    database_url = os.getenv("DATABASE_URL")
    print(f"   DATABASE_URL: {'Set' if database_url else 'NOT SET'}")

    # Test database connection
    print("\n2. Testing database connection...")
    if not database_url:
        print("   ERROR: DATABASE_URL not set")
        return

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()[0]
            print(f"   SUCCESS: Database connection works (returned {test_value})")
    except Exception as e:
        print(f"   ERROR: Database connection failed: {e}")
        return

    # Check database schema
    print("\n3. Checking database schema...")
    try:
        with engine.connect() as conn:
            # Check activities table
            try:
                result = conn.execute(text("SELECT COUNT(*) FROM activities LIMIT 1"))
                count = result.fetchone()[0]
                print(f"   Activities table: {count} records")
            except Exception as e:
                print(f"   ERROR: Activities table issue: {e}")
                return

            # Check run_score column
            try:
                result = conn.execute(text("SELECT run_score FROM activities LIMIT 1"))
                print("   run_score column: EXISTS")
            except Exception as e:
                print(f"   WARNING: run_score column missing: {e}")

            # Check materialized view
            try:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM mv_athlete_metrics LIMIT 1")
                )
                count = result.fetchone()[0]
                print(f"   mv_athlete_metrics view: {count} records")
            except Exception as e:
                print(f"   WARNING: mv_athlete_metrics view missing: {e}")

    except Exception as e:
        print(f"   ERROR: Schema check failed: {e}")
        return

    # Check if backend is running
    print("\n4. Checking if backend is running...")
    try:
        import requests

        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            print("   SUCCESS: Backend is running on localhost:5000")
        else:
            print(f"   WARNING: Backend responded with status {response.status_code}")
    except Exception as e:
        print(f"   ERROR: Backend not reachable: {e}")

    # Check if frontend is running
    print("\n5. Checking if frontend is running...")
    try:
        import requests

        response = requests.get("http://localhost:3000", timeout=5)
        if response.status_code == 200:
            print("   SUCCESS: Frontend is running on localhost:3000")
        else:
            print(f"   WARNING: Frontend responded with status {response.status_code}")
    except Exception as e:
        print(f"   ERROR: Frontend not reachable: {e}")

    print("\nDiagnostic complete!")
    print("\nNext steps:")
    print("1. If database issues: Run the fix script")
    print("2. If backend not running: python run.py")
    print("3. If frontend not running: cd frontend && npm run dev")
    print("4. Check browser console for JavaScript errors")


if __name__ == "__main__":
    main()

