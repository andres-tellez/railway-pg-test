#!/usr/bin/env python3
"""
Investigate and fix v_plan_summary calculation issues
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv(".env.local")

# Add project root to path
project_root = Path(__file__).resolve().parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

from src.db.db_session import get_session
from sqlalchemy import text


def investigate_calculation_issue():
    """Investigate the calculation issue in v_plan_summary"""

    print("=" * 60)
    print("INVESTIGATING v_plan_summary CALCULATION ISSUE")
    print("=" * 60)

    session = get_session()
    try:
        # Get current values from the view
        view_result = session.execute(
            text(
                """
            SELECT
                total_miles,
                total_workouts,
                avg_weekly_miles,
                total_weeks,
                peak_weekly_miles
            FROM v_plan_summary
            LIMIT 1
        """
            )
        ).fetchone()

        print("Current view values:")
        print(f"  total_miles: {view_result.total_miles}")
        print(f"  total_workouts: {view_result.total_workouts}")
        print(f"  avg_weekly_miles: {view_result.avg_weekly_miles}")
        print(f"  total_weeks: {view_result.total_weeks}")
        print(f"  peak_weekly_miles: {view_result.peak_weekly_miles}")

        # Manual calculation to verify
        manual_result = session.execute(
            text(
                """
            SELECT
                SUM(miles) as total_miles,
                COUNT(*) as total_workouts,
                COUNT(DISTINCT DATE_TRUNC('week', date)) as total_weeks,
                MIN(date) as plan_start,
                MAX(date) as plan_end
            FROM plan_workouts
        """
            )
        ).fetchone()

        print("\nManual calculation:")
        print(f"  total_miles: {manual_result.total_miles}")
        print(f"  total_workouts: {manual_result.total_workouts}")
        print(f"  total_weeks: {manual_result.total_weeks}")
        print(f"  plan_start: {manual_result.plan_start}")
        print(f"  plan_end: {manual_result.plan_end}")

        # Calculate expected values
        expected_avg_weekly = (
            manual_result.total_miles / manual_result.total_weeks
            if manual_result.total_weeks > 0
            else 0
        )

        print(f"\nExpected avg_weekly_miles: {expected_avg_weekly}")
        print(f"Actual avg_weekly_miles: {view_result.avg_weekly_miles}")
        print(f"Difference: {abs(expected_avg_weekly - view_result.avg_weekly_miles)}")

        # Check weekly totals to find peak
        weekly_totals = session.execute(
            text(
                """
            SELECT
                DATE_TRUNC('week', date) as week_start,
                SUM(miles) as weekly_miles
            FROM plan_workouts
            GROUP BY DATE_TRUNC('week', date)
            ORDER BY weekly_miles DESC
            LIMIT 5
        """
            )
        ).fetchall()

        print(f"\nTop 5 weekly totals:")
        for week in weekly_totals:
            print(f"  {week.week_start.date()}: {week.weekly_miles} miles")

        expected_peak = weekly_totals[0].weekly_miles if weekly_totals else 0
        print(f"\nExpected peak_weekly_miles: {expected_peak}")
        print(f"Actual peak_weekly_miles: {view_result.peak_weekly_miles}")

        # Identify the issues
        issues = []
        if abs(expected_avg_weekly - view_result.avg_weekly_miles) > 1:
            issues.append(
                f"avg_weekly_miles incorrect: expected {expected_avg_weekly}, got {view_result.avg_weekly_miles}"
            )

        if abs(expected_peak - view_result.peak_weekly_miles) > 1:
            issues.append(
                f"peak_weekly_miles incorrect: expected {expected_peak}, got {view_result.peak_weekly_miles}"
            )

        if issues:
            print(f"\nIssues found:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\nNo calculation issues found!")

        return issues

    except Exception as e:
        print(f"Error during investigation: {e}")
        import traceback

        traceback.print_exc()
        return ["Error during investigation"]
    finally:
        session.close()


def fix_calculation_issues():
    """Fix the calculation issues in v_plan_summary"""

    print("\n" + "=" * 60)
    print("FIXING v_plan_summary CALCULATION ISSUES")
    print("=" * 60)

    session = get_session()
    try:
        # Create the fixed view
        fixed_view_sql = """
        CREATE OR REPLACE VIEW v_plan_summary AS
        SELECT
            p.id as plan_id,
            p.user_id,
            p.plan_name,
            p.race_date,
            p.race_distance,
            p.notes,
            COUNT(pw.id) as total_workouts,
            SUM(pw.miles) as total_miles,
            AVG(pw.miles) as avg_workout_miles,
            MIN(pw.date) as plan_start_date,
            MAX(pw.date) as plan_end_date,
            COUNT(DISTINCT DATE_TRUNC('week', pw.date)) as total_weeks,
            -- Fixed calculation: total_miles / total_weeks
            CASE
                WHEN COUNT(DISTINCT DATE_TRUNC('week', pw.date)) > 0
                THEN SUM(pw.miles) / COUNT(DISTINCT DATE_TRUNC('week', pw.date))
                ELSE 0
            END as avg_weekly_miles,
            -- Fixed peak calculation using subquery
            (SELECT MAX(weekly_miles)
             FROM (
                 SELECT SUM(miles) as weekly_miles
                 FROM plan_workouts pw2
                 WHERE pw2.plan_id = p.id
                 GROUP BY DATE_TRUNC('week', pw2.date)
             ) weekly_totals) as peak_weekly_miles,
            SUM(CASE WHEN pw.workout_type = 'Long Run' THEN pw.miles ELSE 0 END) as total_long_run_miles,
            COUNT(CASE WHEN pw.workout_type = 'Long Run' THEN 1 END) as total_long_runs,
            SUM(CASE WHEN pw.workout_type = 'Easy' THEN pw.miles ELSE 0 END) as total_easy_miles,
            COUNT(CASE WHEN pw.workout_type = 'Easy' THEN 1 END) as total_easy_runs,
            SUM(CASE WHEN pw.workout_type = 'Threshold' THEN pw.miles ELSE 0 END) as total_threshold_miles,
            COUNT(CASE WHEN pw.workout_type = 'Threshold' THEN 1 END) as total_threshold_runs
        FROM plans p
        LEFT JOIN plan_workouts pw ON p.id = pw.plan_id
        GROUP BY p.id, p.user_id, p.plan_name, p.race_date, p.race_distance, p.notes;
        """

        session.execute(text(fixed_view_sql))
        session.commit()

        print("Fixed v_plan_summary view created!")

        # Test the fixed view
        fixed_result = session.execute(
            text(
                """
            SELECT
                total_miles,
                total_workouts,
                avg_weekly_miles,
                total_weeks,
                peak_weekly_miles
            FROM v_plan_summary
            LIMIT 1
        """
            )
        ).fetchone()

        print("\nFixed view values:")
        print(f"  total_miles: {fixed_result.total_miles}")
        print(f"  total_workouts: {fixed_result.total_workouts}")
        print(f"  avg_weekly_miles: {fixed_result.avg_weekly_miles}")
        print(f"  total_weeks: {fixed_result.total_weeks}")
        print(f"  peak_weekly_miles: {fixed_result.peak_weekly_miles}")

        # Verify the fix
        manual_result = session.execute(
            text(
                """
            SELECT
                SUM(miles) as total_miles,
                COUNT(*) as total_workouts,
                COUNT(DISTINCT DATE_TRUNC('week', date)) as total_weeks
            FROM plan_workouts
        """
            )
        ).fetchone()

        expected_avg_weekly = (
            manual_result.total_miles / manual_result.total_weeks
            if manual_result.total_weeks > 0
            else 0
        )

        print(f"\nVerification:")
        print(f"  Expected avg_weekly_miles: {expected_avg_weekly}")
        print(f"  Actual avg_weekly_miles: {fixed_result.avg_weekly_miles}")
        print(
            f"  Difference: {abs(expected_avg_weekly - fixed_result.avg_weekly_miles)}"
        )

        if abs(expected_avg_weekly - fixed_result.avg_weekly_miles) < 0.1:
            print("SUCCESS: Calculation fixed!")
        else:
            print("ISSUE: Calculation still incorrect")

    except Exception as e:
        print(f"Error fixing calculations: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    issues = investigate_calculation_issue()
    if issues:
        fix_calculation_issues()
    else:
        print("No issues found - no fix needed")
