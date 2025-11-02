#!/usr/bin/env python
"""
Scheduler for weekly maintenance tasks - runs on a configurable schedule.
This is a long-running process that Railway runs as a worker.

Tasks:
1. Metrics refresh - refreshes materialized views and invalidates caches
2. Weekly plan rebuild - rebuilds upcoming week's workouts for all active plans
3. Email notifications - sends weekly update emails to users with changes

Schedule is configured via SCHEDULE_* constants at the top of this file.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, date, timezone
from typing import Optional, List, Dict, Any
import pytz
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Immediate startup output for Railway
print("=" * 80, flush=True)
print("[SCHEDULER] Weekly Metrics Scheduler Starting...", flush=True)
print(f"[SCHEDULER] Project root: {project_root}", flush=True)
print("=" * 80, flush=True)

# Load environment variables from .env.local if it exists
env_local_path = project_root / ".env.local"
if env_local_path.exists():
    load_dotenv(env_local_path, override=True)
    print(f"[SCHEDULER] Loaded environment from .env.local", flush=True)
else:
    # Try .env.staging as fallback
    env_staging_path = project_root / ".env.staging"
    if env_staging_path.exists():
        load_dotenv(env_staging_path, override=True)
        print(f"[SCHEDULER] Loaded environment from .env.staging", flush=True)
    else:
        print(
            f"[SCHEDULER] No .env.local or .env.staging found - using system environment",
            flush=True,
        )

# Configure logging
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# SCHEDULE CONFIGURATION - Update these values to change the schedule
# ============================================================================
SCHEDULE_WEEKDAY = 6  # Sunday (0=Monday, 6=Sunday)
SCHEDULE_HOUR = 13  # Hour (24-hour format: 13 = 1 PM)
SCHEDULE_MINUTE = 45  # Minute (0-59)
SCHEDULE_TIMEZONE = "America/Chicago"  # Central Time
SCHEDULE_TIMEZONE_DISPLAY = "Central Time"  # Display name for logs

# Format string for displaying the schedule
SCHEDULE_DISPLAY = (
    f"Sunday at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} {SCHEDULE_TIMEZONE_DISPLAY}"
)


# ============================================================================
# CENTRALIZED TIME FUNCTIONS - Use these instead of datetime.utcnow()
# ============================================================================
def get_current_utc_time() -> datetime:
    """Get current UTC time (replaces deprecated datetime.utcnow())."""
    return datetime.now(timezone.utc)


def get_current_local_time() -> datetime:
    """
    Get current time in configured timezone (SCHEDULE_TIMEZONE).
    Returns timezone-naive datetime for compatibility.
    """
    use_utc = os.getenv("USE_UTC_TIME", "false").lower() == "true"

    if use_utc:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        # Get timezone-aware UTC datetime
        utc_now = datetime.now(timezone.utc)
        # Convert to pytz UTC first, then to target timezone
        pytz_utc = pytz.UTC
        tz = pytz.timezone(SCHEDULE_TIMEZONE)
        # Convert timezone-aware UTC to target timezone, then remove tzinfo
        local_with_tz = utc_now.replace(tzinfo=pytz_utc).astimezone(tz)
        return local_with_tz.replace(tzinfo=None)


def should_run_scheduled_tasks():
    """Check if it's time to run scheduled tasks based on SCHEDULE_* configuration."""
    now = get_current_local_time()

    # Check if it matches the configured schedule
    if (
        now.weekday() == SCHEDULE_WEEKDAY
        and now.hour == SCHEDULE_HOUR
        and now.minute == SCHEDULE_MINUTE
    ):
        return True

    # For development/testing: allow manual trigger via environment variable
    # Set ENABLE_WEEKLY_TASKS=true to trigger on the next check (within the hour)
    if os.getenv("ENABLE_WEEKLY_TASKS", "false").lower() == "true":
        # Clear the flag so it only runs once
        os.environ.pop("ENABLE_WEEKLY_TASKS", None)
        return True

    return False


def run_metrics_refresh():
    """Import and run the metrics refresh script."""
    import time

    start_time = time.time()

    try:
        logger.info("🔄 Step 1/3: Starting metrics refresh...")
        logger.info("   [This may take 2-5 minutes depending on data size]")

        from src.scripts.refresh_metrics_cron import main as refresh_main

        logger.info("   [Calling refresh_metrics_cron.main()...]")
        exit_code = refresh_main()

        elapsed = time.time() - start_time
        logger.info(f"   [Metrics refresh took {elapsed:.1f} seconds]")

        if exit_code == 0:
            logger.info("✅ Metrics refresh completed successfully")
            return (
                True,
                "Metrics dashboard successfully refreshed. All graphs updated with latest data.",
            )
        else:
            logger.error("❌ Metrics refresh completed with errors")
            return (
                False,
                "Metrics refresh encountered errors. Some graphs may not be updated.",
            )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            f"❌ Error running metrics refresh after {elapsed:.1f} seconds: {e}"
        )
        import traceback

        logger.error(traceback.format_exc())
        return False, f"Metrics refresh failed: {str(e)}"


def fetch_last_week_actual_runs(
    session, user_id: str, week_start_date: date
) -> Dict[str, Dict[str, Any]]:
    """
    Fetch actual completed runs from last week, grouped by day of week.

    Args:
        session: Database session
        user_id: User UUID string
        week_start_date: Monday of the upcoming week (to calculate previous week)

    Returns:
        Dict mapping day names to run details: {"Monday": {...}, "Tuesday": {...}, ...}
    """
    from datetime import datetime
    from sqlalchemy import and_
    from src.db.models.activities import Activity

    # Calculate last week's date range (Monday to Sunday)
    last_week_end = week_start_date - timedelta(days=1)  # Sunday
    last_week_start = last_week_end - timedelta(days=6)  # Monday

    # Convert to datetime for query
    last_week_start_dt = datetime.combine(last_week_start, datetime.min.time())
    last_week_end_dt = datetime.combine(last_week_end, datetime.max.time())

    try:
        # Fetch activities from last week
        activities = (
            session.query(Activity)
            .filter(
                and_(
                    Activity.user_id == user_id,
                    Activity.type == "Run",
                    Activity.start_date >= last_week_start_dt,
                    Activity.start_date <= last_week_end_dt,
                )
            )
            .order_by(Activity.start_date)
            .all()
        )

        # Group by day of week
        runs_by_day = {}
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for day_name in day_names:
            runs_by_day[day_name] = None  # Initialize as None (no run)

        for activity in activities:
            if not activity.start_date:
                continue

            # Get day of week (0=Monday, 6=Sunday)
            day_of_week = activity.start_date.weekday()
            day_name = day_names[day_of_week]

            # Format pace from average_speed (m/s) to MM:SS/mi
            pace_str = "N/A"
            if activity.average_speed and activity.average_speed > 0:
                # Convert m/s to seconds per mile
                seconds_per_mile = 1609.34 / activity.average_speed
                minutes = int(seconds_per_mile // 60)
                seconds = int(seconds_per_mile % 60)
                pace_str = f"{minutes}:{seconds:02d}/mi"

            distance_mi = activity.conv_distance or (
                activity.distance / 1609.34 if activity.distance else 0
            )

            runs_by_day[day_name] = {
                "distance": round(distance_mi, 1),
                "pace": pace_str,
                "name": activity.name or "Run",
                "date": (
                    activity.start_date.date().isoformat()
                    if activity.start_date
                    else ""
                ),
            }

        logger.info(f"📊 Fetched {len(activities)} actual runs from last week")
        return runs_by_day

    except Exception as e:
        logger.warning(f"⚠️  Could not fetch last week actual runs: {e}")
        return {}


def calculate_upcoming_week_num(race_date: date, today: date) -> Optional[int]:
    """
    Calculate the week number for the upcoming week (starts next Monday).

    Args:
        race_date: Race date
        today: Current date

    Returns:
        Week number (1-based) or None if race has passed or week not found
    """
    # Calculate next Monday (start of upcoming week)
    # If today is Sunday, next Monday is tomorrow
    # If today is Monday-Saturday, next Monday is days until next Monday
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # Today is Monday, next Monday is 7 days away
    upcoming_monday = today + timedelta(days=days_until_monday)

    # Calculate weeks until race from upcoming Monday
    days_until_race = (race_date - upcoming_monday).days

    # If race has already passed or is less than a week away, don't rebuild
    if days_until_race < 7:
        return None

    # Calculate week number (weeks before race week)
    # Week 1 = first week before race week, Week 2 = second week, etc.
    weeks_until_race = days_until_race // 7

    # Week numbering: if there are 16 weeks until race,
    # Week 1 starts 15 weeks before race week (since week 0 is race week)
    # So week_num = weeks_until_race (when weeks_until_race > 0)
    week_num = weeks_until_race

    return week_num if week_num > 0 else None


def run_weekly_rebuild(metrics_refresh_success: bool, metrics_message: str):
    """Rebuild upcoming week for all active plans and send email notifications."""
    import time

    start_time = time.time()

    try:
        logger.info("🔄 Step 2/3: Starting weekly plan rebuild...")

        from src.db.db_session import get_session
        from src.db.models.plans import Plan
        from src.db.models.user_identity import UserIdentity
        from src.db.models.activities import Activity
        from src.services.training_plan.weekly_rebuild_service import (
            WeeklyRebuildService,
        )
        from src.services.training_plan.week_log_service import (
            fetch_week_logs_from_db,
        )
        from src.services.email_service import EmailService

        logger.info("   [Imports successful, querying database...]")

        session = get_session()
        try:
            # Get all active plans
            active_plans = session.query(Plan).filter_by(is_active=True).all()

            if not active_plans:
                logger.info("ℹ️  No active plans found - skipping rebuild")
                return 0

            logger.info(f"📋 Found {len(active_plans)} active plan(s)")

            today = date.today()
            rebuild_service = WeeklyRebuildService()
            rebuilt_count = 0
            skipped_count = 0
            error_count = 0
            emails_sent = 0
            emails_failed = 0

            for plan in active_plans:
                try:
                    if not plan.race_date:
                        logger.warning(f"⚠️  Plan {plan.id} has no race_date - skipping")
                        skipped_count += 1
                        continue

                    # Calculate upcoming week number
                    upcoming_week_num = calculate_upcoming_week_num(
                        plan.race_date, today
                    )

                    if upcoming_week_num is None:
                        logger.debug(
                            f"ℹ️  Plan {plan.id}: No upcoming week to rebuild "
                            f"(race_date: {plan.race_date})"
                        )
                        skipped_count += 1
                        continue

                    logger.info(
                        f"🔧 Rebuilding week {upcoming_week_num} for plan {plan.id} "
                        f"(race_date: {plan.race_date})"
                    )

                    # Fetch previous week logs (for pace adjustments)
                    previous_week_logs = []
                    if upcoming_week_num > 1:
                        try:
                            logger.info(f"   [Fetching previous week logs...]")
                            previous_week_logs = fetch_week_logs_from_db(
                                session=session,
                                plan_id=plan.id,
                                week_num=upcoming_week_num - 1,
                                race_date=plan.race_date,
                            )
                            logger.info(
                                f"📊 Fetched {len(previous_week_logs)} logs from previous week"
                            )
                        except Exception as e:
                            logger.warning(
                                f"⚠️  Could not fetch previous week logs: {e} "
                                f"(continuing without pace adjustments)"
                            )

                    # Rebuild the week
                    logger.info(
                        f"   [Starting rebuild for plan {plan.id}, week {upcoming_week_num}...]"
                    )
                    logger.info(
                        f"   [NOTE: This may take 1-3 minutes - fetching Strava data & generating workout details]"
                    )
                    rebuild_start = time.time()
                    result = rebuild_service.rebuild_week(
                        session=session,
                        plan_id=plan.id,
                        week_num=upcoming_week_num,
                        previous_week_logs=previous_week_logs,
                        initial_seed=None,  # Will regenerate from plan
                    )
                    rebuild_elapsed = time.time() - rebuild_start
                    logger.info(
                        f"   [Rebuild completed for plan {plan.id} in {rebuild_elapsed:.1f} seconds]"
                    )

                    session.commit()

                    # Get workout changes from result
                    workout_changes = result.get("workout_changes", [])

                    logger.info(
                        f"✅ Successfully rebuilt week {upcoming_week_num} for plan {plan.id} "
                        f"(pace_adjusted={result.get('pace_adjusted', False)}, "
                        f"{len(workout_changes)} workouts changed)"
                    )
                    rebuilt_count += 1

                    # Send email notification
                    try:
                        # Get user email from user_identity table
                        user_identity = (
                            session.query(UserIdentity)
                            .filter_by(user_id=str(plan.user_id))
                            .first()
                        )

                        if user_identity and user_identity.email:
                            # Calculate week start date for display
                            days_until_monday = (7 - today.weekday()) % 7
                            if days_until_monday == 0:
                                days_until_monday = 7
                            week_start_date_obj = today + timedelta(
                                days=days_until_monday
                            )
                            week_start_date = week_start_date_obj.isoformat()

                            # Fetch last week's actual runs
                            last_week_runs = {}
                            try:
                                last_week_runs = fetch_last_week_actual_runs(
                                    session=session,
                                    user_id=str(plan.user_id),
                                    week_start_date=week_start_date_obj,
                                )
                            except Exception as e:
                                logger.warning(
                                    f"⚠️  Could not fetch last week runs for email: {e}"
                                )

                            # Get original and updated workouts from rebuild result
                            original_workouts = result.get("original_workouts", [])
                            updated_workouts = result.get("updated_workouts", [])

                            # Send email
                            email_sent = EmailService.send_weekly_update_email(
                                to_email=user_identity.email,
                                user_name=user_identity.name,
                                week_num=upcoming_week_num,
                                week_start=week_start_date,
                                last_week_actual_runs=last_week_runs,
                                next_week_original_plan=original_workouts,
                                next_week_updated_plan=updated_workouts,
                                metrics_refresh_success=metrics_refresh_success,
                                metrics_refresh_message=metrics_message,
                            )

                            if email_sent:
                                emails_sent += 1
                                logger.info(
                                    f"📧 Email notification sent to {user_identity.email}"
                                )
                            else:
                                emails_failed += 1
                                logger.warning(
                                    f"⚠️  Failed to send email to {user_identity.email}"
                                )
                        else:
                            logger.debug(
                                f"ℹ️  Plan {plan.id}: No email found for user {plan.user_id} - skipping email"
                            )

                    except Exception as e:
                        logger.error(
                            f"❌ Error sending email for plan {plan.id}: {e}",
                            exc_info=True,
                        )
                        emails_failed += 1

                except Exception as e:
                    logger.error(
                        f"❌ Error rebuilding plan {plan.id}: {e}", exc_info=True
                    )
                    session.rollback()
                    error_count += 1

            logger.info(
                f"📊 Weekly rebuild summary: {rebuilt_count} rebuilt, "
                f"{skipped_count} skipped, {error_count} errors, "
                f"{emails_sent} emails sent, {emails_failed} emails failed"
            )

            if error_count > 0:
                return 1
            return 0

        finally:
            session.close()

    except Exception as e:
        logger.error(f"❌ Error in weekly rebuild process: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return 1


def run_all_scheduled_tasks():
    """Run metrics refresh, weekly rebuild, and send email notifications."""
    logger.info(f"🚀 Starting weekly scheduled tasks ({SCHEDULE_DISPLAY})...")

    # Step 1: Metrics refresh
    metrics_success, metrics_message = run_metrics_refresh()

    # Step 2: Weekly rebuild (run even if metrics refresh had issues)
    rebuild_result = run_weekly_rebuild(metrics_success, metrics_message)

    # Return success only if both completed successfully
    if metrics_success and rebuild_result == 0:
        logger.info("✅ All weekly scheduled tasks completed successfully")
        return 0
    else:
        logger.warning(
            "⚠️  Weekly scheduled tasks completed with some errors "
            f"(metrics: {'success' if metrics_success else 'failed'}, rebuild: {rebuild_result})"
        )
        return 1


def main():
    """Main scheduler - supports both worker mode (long-running) and cron mode (run once)."""
    # Immediate output before logging setup
    print("[SCHEDULER] Initializing scheduler...", flush=True)

    # Check if running in "run once" mode (for Railway cron jobs)
    run_once = os.getenv("RUN_ONCE", "false").lower() == "true"

    if run_once:
        # Cron mode: run once and exit
        print("[SCHEDULER] Running in cron mode (run once)...", flush=True)
        logger.info("🚀 Running weekly scheduled tasks (cron mode)...")

        if not os.getenv("DATABASE_URL"):
            print(
                "[SCHEDULER] ERROR: DATABASE_URL not configured. Exiting.", flush=True
            )
            logger.error("❌ DATABASE_URL not configured. Exiting.")
            sys.exit(1)

        exit_code = run_all_scheduled_tasks()
        sys.exit(exit_code)

    # Worker mode: long-running loop (original behavior)
    use_utc = os.getenv("USE_UTC_TIME", "false").lower() == "true"
    timezone_info = "UTC" if use_utc else f"local ({SCHEDULE_TIMEZONE_DISPLAY})"

    print(f"[SCHEDULER] Timezone mode: {timezone_info}", flush=True)
    print(f"[SCHEDULER] Schedule: {SCHEDULE_DISPLAY}", flush=True)
    print(
        f"[SCHEDULER] DATABASE_URL configured: {bool(os.getenv('DATABASE_URL'))}",
        flush=True,
    )

    logger.info(f"🕐 Weekly scheduler started - waiting for {SCHEDULE_DISPLAY}...")
    logger.info(f"💡 Scheduled tasks will run automatically every {SCHEDULE_DISPLAY}")
    # Log current time in both UTC and configured timezone for verification
    utc_now = get_current_utc_time()
    local_now = get_current_local_time()
    use_utc = os.getenv("USE_UTC_TIME", "false").lower() == "true"
    if not use_utc:
        tz = pytz.timezone(SCHEDULE_TIMEZONE)
        # Convert timezone-aware UTC to target timezone
        pytz_utc = pytz.UTC
        local_with_tz = utc_now.replace(tzinfo=pytz_utc).astimezone(tz)
        logger.info(
            f"📍 Current time: UTC={utc_now.strftime('%Y-%m-%d %H:%M:%S')}, "
            f"{SCHEDULE_TIMEZONE_DISPLAY}={local_with_tz.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
    else:
        logger.info(f"📍 Current time (UTC): {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(
        "💡 Tasks include: (1) Metrics refresh, (2) Weekly plan rebuild, (3) Email notifications"
    )
    logger.info(
        "💡 Set ENABLE_WEEKLY_TASKS=true environment variable to manually trigger (for testing)"
    )

    if not os.getenv("DATABASE_URL"):
        print("[SCHEDULER] ERROR: DATABASE_URL not configured. Exiting.", flush=True)
        logger.error("❌ DATABASE_URL not configured. Exiting.")
        sys.exit(1)

    print(
        "[SCHEDULER] DATABASE_URL configured - starting scheduler loop...", flush=True
    )
    print(
        "[SCHEDULER] Scheduler is now running - waiting for scheduled time...",
        flush=True,
    )
    print("=" * 80, flush=True)

    # Track last run to avoid running multiple times
    last_run_timestamp = None

    while True:
        try:
            now = get_current_local_time()

            current_timestamp = now.strftime("%Y-%m-%d %H:%M")

            # Check schedule every minute
            should_run = should_run_scheduled_tasks()

            # Log more frequently when approaching target time for debugging
            if now.weekday() == SCHEDULE_WEEKDAY and now.hour == SCHEDULE_HOUR:
                # On scheduled day/hour, log every minute
                logger.info(
                    f"⏰ {SCHEDULE_DISPLAY} window - Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"(weekday={now.weekday()}, hour={now.hour}, minute={now.minute}), should_run={should_run}"
                )

            if should_run:
                # Only run if we haven't run in this minute already
                if current_timestamp != last_run_timestamp:
                    logger.info(
                        f"⏰ Scheduled time reached - running weekly tasks at {now.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    run_all_scheduled_tasks()
                    last_run_timestamp = current_timestamp
                else:
                    logger.debug(
                        f"⏰ Already ran at {current_timestamp}, skipping duplicate run"
                    )
            else:
                # Log every 10 minutes for debugging
                if now.minute % 10 == 0:
                    logger.info(
                        f"⏰ Checking schedule... (current time: {now.strftime('%Y-%m-%d %H:%M:%S')}, "
                        f"weekday={now.weekday()}, hour={now.hour}, minute={now.minute}) - next run: {SCHEDULE_DISPLAY}"
                    )

            # Sleep for 1 minute before checking again
            time.sleep(60)

        except KeyboardInterrupt:
            logger.info("⏹️  Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Error in scheduler loop: {e}")
            time.sleep(60)  # Wait before retrying


if __name__ == "__main__":
    main()
