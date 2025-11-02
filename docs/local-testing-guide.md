# Local Testing Guide for Weekly Scheduler

## Yes, You CAN Test Locally! ✅

The weekly scheduler can be tested on your local machine. Here's how:

## Quick Test (Manual Trigger)

### Option 1: Environment Variable Trigger

1. **Set the trigger environment variable**:
   ```bash
   # Windows PowerShell
   $env:ENABLE_WEEKLY_TASKS="true"

   # Windows CMD
   set ENABLE_WEEKLY_TASKS=true

   # Mac/Linux
   export ENABLE_WEEKLY_TASKS=true
   ```

2. **Run the scheduler**:
   ```bash
   python src/scripts/metrics_scheduler.py
   ```

3. **It will trigger immediately** (within the next minute check)

4. **Watch the logs** to see:
   - Metrics refresh
   - Weekly rebuild for active plans
   - Email sending (if SMTP configured)

### Option 2: Wait for Scheduled Time

If you want to test at the actual scheduled time:

1. **Run the scheduler**:
   ```bash
   python src/scripts/metrics_scheduler.py
   ```

2. **Wait until Saturday at 10:00 PM Central**

3. **It will automatically run** at that time

## Local Requirements

### 1. Database Connection
Make sure you have `DATABASE_URL` in your `.env.local`:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/database
```

### 2. Email Testing (Optional)
To test email sending locally, add SMTP config to `.env.local`:
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

**Note**: Without SMTP config, emails will be skipped but everything else works!

## What Happens During Testing

1. **Metrics Refresh**:
   - Refreshes materialized views (`mv_athlete_metrics`, `mv_longest_runs`)
   - Invalidates caches
   - Logs success/failure

2. **Weekly Rebuild**:
   - Finds all active plans
   - Calculates upcoming week for each plan
   - Rebuilds workouts with pace adjustments
   - Tracks before/after changes
   - Logs summary

3. **Email Notifications**:
   - Gets user emails from `user_identity` table
   - Sends emails with workout changes
   - Logs success/failure for each email

## Expected Log Output

When you trigger it, you'll see:

```
🕐 Weekly scheduler started - waiting for Saturday at 10:00 PM...
💡 Scheduled tasks will run automatically every Saturday at 10:00 PM Central (local (Central Time))
💡 Set ENABLE_WEEKLY_TASKS=true environment variable to manually trigger (for testing)
⏰ Checking schedule... (current time: 2025-01-11 22:15)
⏰ Scheduled time reached - running weekly tasks at 2025-01-11 22:15:30
🚀 Starting weekly scheduled tasks (Saturday 10 PM Central)...
🔄 Step 1/3: Starting metrics refresh...
✅ Metrics refresh completed successfully
🔄 Step 2/3: Starting weekly plan rebuild...
📋 Found 3 active plan(s)
🔧 Rebuilding week 5 for plan 123...
✅ Successfully rebuilt week 5 for plan 123 (2 workouts changed)
📧 Email notification sent to user@example.com
📊 Weekly rebuild summary: 3 rebuilt, 0 skipped, 0 errors, 3 emails sent, 0 emails failed
✅ All weekly scheduled tasks completed successfully
```

## Troubleshooting Local Testing

### "DATABASE_URL not configured"
**Solution**: Make sure `.env.local` exists with your database URL

### "No active plans found"
**Solution**: This is normal if you don't have active plans. Create a test plan first.

### "Email service not configured"
**Solution**: This is a warning, not an error. Everything else will still work.

### Scheduler Runs But No Output
**Solution**: Check that you have active plans and they have valid race dates.

## Testing in Railway vs Local

### Railway
- ✅ Runs automatically every Saturday 10 PM Central
- ✅ Uses production database
- ✅ Sends real emails
- ✅ Monitored via Railway logs

### Local
- ✅ Can test anytime with `ENABLE_WEEKLY_TASKS=true`
- ✅ Uses local database (your `.env.local` DATABASE_URL)
- ✅ Can test email sending if SMTP configured
- ✅ Same code, same behavior!

**Both work identically!** The scheduler code is the same whether running locally or in Railway.

## Quick Start Commands

```bash
# 1. Activate your virtual environment
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# 2. Set trigger
export ENABLE_WEEKLY_TASKS=true  # Mac/Linux
# or
$env:ENABLE_WEEKLY_TASKS="true"  # Windows PowerShell

# 3. Run scheduler
python src/scripts/metrics_scheduler.py

# 4. Watch logs - it should trigger within 1 minute!
```

## Stopping the Scheduler

Press `Ctrl+C` to stop the scheduler. It's designed to run continuously, so you'll need to interrupt it manually when testing locally.
