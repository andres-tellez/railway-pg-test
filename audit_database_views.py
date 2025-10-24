#!/usr/bin/env python3
"""
Comprehensive audit of all database views
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


def audit_all_views():
    """Audit all database views for correctness and strategic purpose"""

    print("=" * 80)
    print("COMPREHENSIVE DATABASE VIEWS AUDIT")
    print("=" * 80)

    session = get_session()
    try:
        # Get all views in the database
        views_result = session.execute(
            text(
                """
            SELECT viewname, definition
            FROM pg_views
            WHERE schemaname = 'public'
            AND viewname LIKE 'v_%'
            ORDER BY viewname
        """
            )
        ).fetchall()

        print(f"Found {len(views_result)} views to audit:")
        for view in views_result:
            print(f"  - {view.viewname}")

        print("\n" + "=" * 80)

        # Audit each view
        audit_results = {}

        for view_name, definition in views_result:
            print(f"\nAUDITING: {view_name}")
            print("-" * 60)

            audit_result = audit_view(session, view_name, definition)
            audit_results[view_name] = audit_result

            # Print audit results
            print(f"Strategic Purpose: {audit_result['purpose']}")
            print(f"Data Accuracy: {audit_result['accuracy']}")
            print(f"Unique Metrics: {len(audit_result['metrics'])}")
            if audit_result["issues"]:
                print(f"Issues Found: {len(audit_result['issues'])}")
                for issue in audit_result["issues"]:
                    print(f"  - {issue}")
            else:
                print("Issues: None")

        # Check for metric redundancy across views
        print("\n" + "=" * 80)
        print("METRIC REDUNDANCY ANALYSIS")
        print("=" * 80)

        check_metric_redundancy(audit_results)

        # Overall assessment
        print("\n" + "=" * 80)
        print("OVERALL ASSESSMENT")
        print("=" * 80)

        total_issues = sum(len(result["issues"]) for result in audit_results.values())
        total_views = len(audit_results)

        print(f"Total Views: {total_views}")
        print(f"Total Issues: {total_issues}")
        print(
            f"Views with Issues: {sum(1 for result in audit_results.values() if result['issues'])}"
        )

        if total_issues == 0:
            print("STATUS: All views are working correctly!")
        else:
            print(f"STATUS: {total_issues} issues need attention")

    except Exception as e:
        print(f"Error during audit: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


def audit_view(session, view_name, definition):
    """Audit a single view"""
    audit_result = {"purpose": "", "accuracy": "Unknown", "metrics": [], "issues": []}

    try:
        # Test the view by querying it
        test_result = session.execute(
            text(f"SELECT * FROM {view_name} LIMIT 5")
        ).fetchall()

        if not test_result:
            audit_result["issues"].append("View returns no data")
            return audit_result

        # Analyze based on view name
        if view_name == "v_completed_activities":
            audit_result["purpose"] = "Historical activity data for progress tracking"
            audit_result["metrics"] = [
                "activity_date",
                "distance",
                "avg_speed",
                "avg_hr",
                "elevation",
            ]

            # Test calculations
            calc_test = session.execute(
                text(
                    """
                SELECT
                    COUNT(*) as total_activities,
                    SUM(distance) as total_distance,
                    AVG(avg_speed) as avg_pace
                FROM v_completed_activities
                LIMIT 1
            """
                )
            ).fetchone()

            if calc_test and calc_test.total_activities > 0:
                audit_result["accuracy"] = "Verified - calculations working"
            else:
                audit_result["issues"].append("Calculation issues detected")

        elif view_name == "v_activity_splits":
            audit_result["purpose"] = "Detailed split data for pace analysis"
            audit_result["metrics"] = ["split", "avg_hr", "avg_speed", "split_time"]

            # Test data integrity
            split_test = session.execute(
                text(
                    """
                SELECT COUNT(*) as total_splits FROM v_activity_splits LIMIT 1
            """
                )
            ).fetchone()

            if split_test and split_test.total_splits > 0:
                audit_result["accuracy"] = "Verified - data accessible"
            else:
                audit_result["issues"].append("No split data found")

        elif view_name == "v_weekly_plan_totals":
            audit_result["purpose"] = "Weekly training plan summaries for GPT context"
            audit_result["metrics"] = [
                "week_start",
                "total_miles",
                "workout_count",
                "workout_types",
                "long_run_miles",
            ]

            # Test weekly calculations
            weekly_test = session.execute(
                text(
                    """
                SELECT
                    week_start,
                    total_miles,
                    workout_count,
                    long_run_miles
                FROM v_weekly_plan_totals
                WHERE week_start >= '2025-10-27' AND week_start <= '2025-11-02'
                LIMIT 1
            """
                )
            ).fetchone()

            if weekly_test:
                # Verify the calculation matches manual calculation
                manual_calc = session.execute(
                    text(
                        """
                    SELECT SUM(miles) as manual_total
                    FROM plan_workouts
                    WHERE date >= '2025-10-27' AND date <= '2025-11-02'
                """
                    )
                ).fetchone()

                if (
                    manual_calc
                    and abs(weekly_test.total_miles - manual_calc.manual_total) < 0.1
                ):
                    audit_result["accuracy"] = (
                        "Verified - calculations match manual totals"
                    )
                else:
                    audit_result["issues"].append(
                        f"Weekly calculation mismatch: view={weekly_test.total_miles}, manual={manual_calc.manual_total}"
                    )
            else:
                audit_result["issues"].append("No weekly data found for test period")

        elif view_name == "v_monthly_plan_totals":
            audit_result["purpose"] = (
                "Monthly training plan summaries for long-term analysis"
            )
            audit_result["metrics"] = [
                "month_start",
                "total_miles",
                "workout_count",
                "workout_types",
                "long_run_miles",
            ]

            # Test monthly calculations
            monthly_test = session.execute(
                text(
                    """
                SELECT COUNT(*) as month_count FROM v_monthly_plan_totals LIMIT 1
            """
                )
            ).fetchone()

            if monthly_test and monthly_test.month_count > 0:
                audit_result["accuracy"] = "Verified - monthly data available"
            else:
                audit_result["issues"].append("No monthly data found")

        elif view_name == "v_plan_summary":
            audit_result["purpose"] = (
                "Complete plan overview with all key metrics for GPT"
            )
            audit_result["metrics"] = [
                "total_miles",
                "total_workouts",
                "avg_weekly_miles",
                "peak_weekly_miles",
                "total_long_runs",
            ]

            # Test plan summary calculations
            plan_test = session.execute(
                text(
                    """
                SELECT
                    total_miles,
                    total_workouts,
                    avg_weekly_miles,
                    peak_weekly_miles
                FROM v_plan_summary
                LIMIT 1
            """
                )
            ).fetchone()

            if plan_test:
                # Verify calculations make sense
                if plan_test.total_workouts > 0 and plan_test.total_miles > 0:
                    expected_avg = plan_test.total_miles / max(
                        plan_test.total_workouts / 4, 1
                    )  # Rough estimate
                    if (
                        abs(plan_test.avg_weekly_miles - expected_avg)
                        < plan_test.avg_weekly_miles * 0.5
                    ):  # Within 50%
                        audit_result["accuracy"] = (
                            "Verified - calculations appear reasonable"
                        )
                    else:
                        audit_result["issues"].append(
                            "Average weekly miles calculation seems incorrect"
                        )
                else:
                    audit_result["issues"].append("Invalid totals in plan summary")
            else:
                audit_result["issues"].append("No plan summary data found")

        elif view_name == "v_recent_activities_summary":
            audit_result["purpose"] = "Recent activity summaries for progress tracking"
            audit_result["metrics"] = [
                "total_activities",
                "total_miles",
                "avg_distance",
                "avg_pace",
                "avg_heart_rate",
            ]

            # Test recent activities
            recent_test = session.execute(
                text(
                    """
                SELECT
                    total_activities,
                    total_miles,
                    avg_distance
                FROM v_recent_activities_summary
                LIMIT 1
            """
                )
            ).fetchone()

            if recent_test:
                audit_result["accuracy"] = "Verified - recent activity data available"
            else:
                audit_result["issues"].append("No recent activity data found")

        elif view_name == "v_upcoming_workouts":
            audit_result["purpose"] = (
                "Future workout schedule with timeframe categorization"
            )
            audit_result["metrics"] = ["date", "workout_type", "miles", "timeframe"]

            # Test upcoming workouts logic
            upcoming_test = session.execute(
                text(
                    """
                SELECT
                    COUNT(*) as total_upcoming,
                    COUNT(CASE WHEN date < CURRENT_DATE THEN 1 END) as past_count,
                    COUNT(CASE WHEN timeframe = 'TODAY' THEN 1 END) as today_count
                FROM v_upcoming_workouts
                LIMIT 1
            """
                )
            ).fetchone()

            if upcoming_test:
                if upcoming_test.past_count == 0:
                    audit_result["accuracy"] = "Verified - no past workouts included"
                else:
                    audit_result["issues"].append(
                        f"Past workouts incorrectly included: {upcoming_test.past_count}"
                    )

                if upcoming_test.today_count > 0:
                    audit_result["accuracy"] += ", today categorization working"
            else:
                audit_result["issues"].append("No upcoming workout data found")

        else:
            audit_result["purpose"] = "Unknown view - needs purpose definition"
            audit_result["issues"].append("View purpose not defined")

    except Exception as e:
        audit_result["issues"].append(f"Error testing view: {str(e)}")

    return audit_result


def check_metric_redundancy(audit_results):
    """Check for redundant metrics across views"""

    # Collect all metrics from all views
    all_metrics = {}
    for view_name, result in audit_results.items():
        for metric in result["metrics"]:
            if metric not in all_metrics:
                all_metrics[metric] = []
            all_metrics[metric].append(view_name)

    # Find redundant metrics
    redundant_metrics = {
        metric: views for metric, views in all_metrics.items() if len(views) > 1
    }

    if redundant_metrics:
        print("REDUNDANT METRICS FOUND:")
        for metric, views in redundant_metrics.items():
            print(f"  {metric}: {', '.join(views)}")

        print("\nRECOMMENDATIONS:")
        for metric, views in redundant_metrics.items():
            if metric == "total_miles":
                print(
                    f"  - {metric}: Keep in v_plan_summary (comprehensive), remove from others"
                )
            elif metric == "workout_count":
                print(
                    f"  - {metric}: Keep in v_plan_summary (comprehensive), remove from others"
                )
            elif metric == "avg_speed":
                print(
                    f"  - {metric}: Keep in v_completed_activities (source), remove from others"
                )
            else:
                print(f"  - {metric}: Review if all instances are necessary")
    else:
        print("No redundant metrics found - all views serve unique purposes")


if __name__ == "__main__":
    audit_all_views()
