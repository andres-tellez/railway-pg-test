#!/usr/bin/env python
"""
Scheduler for metrics refresh - runs the refresh script every Monday at 2:00 AM Central.
This is a long-running process that Railway runs as a worker.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def should_run_refresh():
    """Check if it's Monday at 2:00 AM (or within the 2:00-3:00 AM window)."""
    # Use local time (Central Time) for scheduling
    import os

    use_utc = os.getenv("USE_UTC_TIME", "false").lower() == "true"
    now = datetime.utcnow() if use_utc else datetime.now()

    # It's Monday (weekday 0) and between 2:00 and 3:00 AM
    if now.weekday() == 0 and now.hour == 2:
        return True

    # For development/testing: allow manual trigger via environment variable
    # Set ENABLE_REFRESH=true to trigger refresh on the next check (within the hour)
    if os.getenv("ENABLE_REFRESH", "false").lower() == "true":
        # Clear the flag so it only runs once
        os.environ.pop("ENABLE_REFRESH", None)
        return True

    return False


def run_refresh():
    """Import and run the refresh script."""
    try:
        from src.scripts.refresh_metrics_cron import main as refresh_main

        logger.info("🚀 Triggering metrics refresh...")
        exit_code = refresh_main()

        if exit_code == 0:
            logger.info("✅ Metrics refresh completed successfully")
        else:
            logger.error("❌ Metrics refresh completed with errors")

        return exit_code
    except Exception as e:
        logger.error(f"❌ Error running refresh: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return 1


def main():
    """Main scheduler loop - runs forever."""
    import os

    use_utc = os.getenv("USE_UTC_TIME", "false").lower() == "true"
    timezone_info = "UTC" if use_utc else "local (Central Time)"

    logger.info("🕐 Metrics scheduler started - waiting for Monday at 2:00 AM...")
    logger.info(
        f"💡 The refresh will run automatically every Monday at 2:00 AM Central ({timezone_info})"
    )
    logger.info(
        "💡 Set ENABLE_REFRESH=true environment variable to manually trigger (for testing)"
    )

    # Track last check to avoid running multiple times in the same hour
    last_check_day = None

    while True:
        try:
            now = datetime.utcnow() if use_utc else datetime.now()
            current_day = now.strftime("%Y-%m-%d %H")

            # Only check once per hour to avoid spam
            if current_day != last_check_day:
                logger.debug(
                    f"⏰ Checking schedule... (current time: {now.strftime('%Y-%m-%d %H:%M')})"
                )
                last_check_day = current_day

                if should_run_refresh():
                    logger.info(
                        f"⏰ Scheduled time reached - running metrics refresh at {now}"
                    )
                    run_refresh()
                else:
                    logger.debug(
                        f"⏰ Not time yet - next refresh: Monday at 2:00 AM Central"
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
    # Make sure we have required env vars
    if not os.getenv("DATABASE_URL"):
        logger.error("❌ DATABASE_URL not configured. Exiting.")
        sys.exit(1)

    main()
