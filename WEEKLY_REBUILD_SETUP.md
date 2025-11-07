# Weekly Rebuild Setup Guide

## Current Status

### ✅ What's Complete

1. **Draft Preview** (`/api/plan/draft`)

   - Generates a complete plan with workout details
   - Returns plan for user to preview
   - **Does NOT save to database**

2. **Plan Approval** (`/api/plan/approve`)

   - User saves the draft after reviewing
   - Calls `PlanStorageService.save_validated_plan()`
   - Stores plan and all workouts in database

3. **Weekly Rebuild Endpoint** (`POST /api/plan/<plan_id>/week/<week_num>/rebuild`)
   - Manually rebuilds a specific week's workout details
   - Adjusts pace based on previous week's logs (RPE, completion, HR)
   - Updates workout segments and cues
   - **Requires:**
     - `plan_id`: ID of the plan
     - `week_num`: Week number to rebuild
     - `previous_week_logs`: Optional dict with previous week's workout logs

### ❌ What's Missing

**Automated Weekly Rebuild Trigger**

The weekly rebuild endpoint exists but has no automated trigger. You need to choose one of these approaches:

## Option 1: Scheduled Cron Job (Recommended)

Create a scheduled job that runs weekly (e.g., Sunday at 6 PM) to rebuild the upcoming week for all active plans.

### Implementation Steps:

1. **Create a scheduler script** (`src/scripts/weekly_rebuild_scheduler.py`):

   ```python
   """
   Scheduler for weekly plan rebuilds.
   Runs every Sunday at 6 PM to rebuild the upcoming week for all active plans.
   """
   import os
   import sys
   from pathlib import Path
   from datetime import datetime, timedelta
   from sqlalchemy.orm import Session

   project_root = Path(__file__).parent.parent.parent
   sys.path.insert(0, str(project_root))

   from src.db.db_session import get_session
   from src.db.models.plans import Plan
   from src.services.training_plan.weekly_rebuild_service import WeeklyRebuildService
   from src.services.training_plan.week_log_service import WeekLogService

   def should_rebuild_week(plan: Plan, week_num: int) -> bool:
       """Check if week_num is the upcoming week for this plan."""
       race_date = plan.race_date
       today = datetime.now().date()

       # Calculate week start date
       weeks_until_race = (race_date - today).days / 7
       weeks_until_week = weeks_until_race - (week_num - 1)

       # Rebuild if week is starting within 1-3 days
       return 0 <= weeks_until_week * 7 <= 3

   def rebuild_upcoming_weeks():
       """Rebuild upcoming week for all active plans."""
       session = get_session()
       try:
           active_plans = session.query(Plan).filter_by(is_active=True).all()
           rebuild_service = WeeklyRebuildService()
           log_service = WeekLogService()

           for plan in active_plans:
               # Determine which week to rebuild
               race_date = plan.race_date
               today = datetime.now().date()
               days_until_race = (race_date - today).days
               weeks_until_race = days_until_race / 7

               # Rebuild week that starts this week
               upcoming_week_num = int(weeks_until_race) + 1

               if upcoming_week_num >= 1:
                   # Fetch previous week logs
                   previous_week_logs = log_service.fetch_week_logs_from_db(
                       session=session,
                       plan_id=plan.id,
                       week_num=upcoming_week_num - 1,
                   )

                   # Rebuild week
                   result = rebuild_service.rebuild_week(
                       session=session,
                       plan_id=plan.id,
                       week_num=upcoming_week_num,
                       previous_week_logs=previous_week_logs,
                       initial_seed=None,
                   )

                   session.commit()
                   logger.info(f"Rebuilt week {upcoming_week_num} for plan {plan.id}")
       finally:
           session.close()

   if __name__ == "__main__":
       rebuild_upcoming_weeks()
   ```

2. **Add to Railway Procfile or cron job**:
   - Railway: Add worker process
   - Cron: Schedule to run weekly (Sunday 6 PM)

## Option 2: Frontend-Triggered (User Action)

Have the frontend call the rebuild endpoint when:

- User opens the plan for the current week
- User completes a week and clicks "Next Week"
- Weekly reminder notification is clicked

### Implementation Steps:

1. **Add frontend logic** to detect when a week needs rebuilding
2. **Call rebuild endpoint** before displaying week details
3. **Update UI** after rebuild completes

## Option 3: Webhook-Based (Strava Activity Complete)

Trigger rebuild when:

- Strava webhook indicates user completed all workouts for a week
- User logs completion through your app

### Implementation Steps:

1. **Extend webhook handler** to detect week completion
2. **Call rebuild service** automatically
3. **Notify user** that next week is ready

## Recommended Approach

**Option 1 (Scheduled Cron)** is recommended because:

- ✅ Automatic - no user action required
- ✅ Consistent - runs at same time every week
- ✅ Reliable - doesn't depend on user behavior
- ✅ Can rebuild multiple plans efficiently

**Implementation Priority:**

1. Create the scheduler script
2. Add Railway worker or cron job
3. Test with a single plan
4. Monitor logs for errors
5. Add alerting for failures

## Testing

Before deploying:

1. Test rebuild endpoint manually: `POST /api/plan/<plan_id>/week/<week_num>/rebuild`
2. Verify pace adjustments work correctly
3. Check that previous week logs are fetched correctly
4. Ensure workout details are updated in database

## Future Enhancements

- Add notification to user when week is rebuilt
- Allow user to override rebuild timing
- Add analytics on rebuild frequency and adjustments
- Support for partial rebuilds (single workout)
