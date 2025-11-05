# How to Remove Railway Cron Job for Webhook Health Alert

## ✅ Codebase Cleanup Complete

All code references to `webhook_health_alert` have been removed from the repository.

## Manual Step Required: Remove Cron Job from Railway Dashboard

Railway cron jobs are configured in the Railway dashboard UI, not in code. You need to manually remove it.

### Step-by-Step Instructions

1. **Go to Railway Dashboard**
   - Visit: https://railway.app
   - Select your project
   - Select your **staging backend** service (or the service that has the cron job)

2. **Navigate to Cron Jobs**
   - In the service settings, look for:
     - **"Cron Jobs"** section
     - **"Scheduled Tasks"** section
     - **"Settings" → "Cron"** tab

3. **Find the Webhook Health Alert Cron Job**
   - Look for a cron job with:
     - **Command**: `python -m src.scripts.webhook_health_alert`
     - **Schedule**: Likely `0 9 * * *` (daily at 9 AM UTC) or similar

4. **Delete the Cron Job**
   - Click the **"Delete"** or **"Remove"** button
   - Confirm deletion

### Alternative: Check via Railway CLI

If you have Railway CLI installed:

```bash
# List all services
railway status

# Check cron jobs (if Railway CLI supports this)
railway cron list
```

### Verification

After removing the cron job:

1. ✅ Check Railway logs - should no longer see `webhook_health_alert` runs
2. ✅ Verify no cron job errors appear
3. ✅ Monitor webhooks via `/webhooks/strava/status` endpoint instead

## What to Look For

The cron job you're looking for should have:
- **Command**: `python -m src.scripts.webhook_health_alert`
- **Purpose**: Webhook health monitoring with alerts
- **Status**: Will fail now that the script is deleted

## If You Can't Find It

If you don't see a cron job configured:
- ✅ **Good news**: It was never set up, or already removed
- The script has been deleted from code, so even if it exists, it will fail
- No action needed

## Notes

- Railway cron jobs are service-specific
- You may need to check multiple services (backend, cron service, etc.)
- Some Railway projects use scheduled tasks instead of cron jobs
- The cron job might be in a separate "cron" or "scheduler" service
