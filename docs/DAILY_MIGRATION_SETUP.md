# Daily Migration Setup: Production to Local Database

This guide shows how to set up a daily scheduled migration that copies data from production to your local development database.

## 🎯 Overview

The daily migration scheduler runs automatically at **1 AM Central Time** to sync production data to your local database. This keeps your local development environment up-to-date with the latest production data.

## 🚀 Setup: Railway Cron Job

### Step 1: Add Cron Job in Railway

1. Go to Railway Dashboard: https://railway.app
2. Select your project
3. Go to **Settings** (gear icon)
4. Scroll to **Cron Jobs** section
5. Click **+ Add Cron Job**

### Step 2: Configure the Cron Job

**Schedule:**
```
0 7 * * *
```
(This runs every day at **07:00 UTC**, which is **1:00 AM Central Time (CST)**)

**Note on DST:**
- **CST (winter)**: 1 AM CST = 7 AM UTC ✅
- **CDT (summer)**: 1 AM CDT = 6 AM UTC (runs 1 hour earlier during summer)
- Using `0 7 * * *` means it runs at 1 AM CST, but 12 AM CDT during summer (1 hour earlier)

**Command:**
```
RUN_ONCE=true python src/scripts/daily_migration_scheduler.py
```

### Step 3: Set Environment Variables

Make sure these environment variables are set in Railway:

**Required:**
- `PROD_DATABASE_URL` - Production database connection string
- `DATABASE_URL` - Local database connection string
- `ENABLE_PROD_TO_LOCAL_MIGRATION=true` - Enable flag (must be set to "true")

**Optional:**
- `SOURCE_ATHLETE_ID` - Source athlete ID to copy (default: 347085)
- `TARGET_ATHLETE_ID` - Target athlete ID in local DB (default: 347085)

### Step 4: Save

Click **Save** and Railway will start running the job automatically.

---

## 🧪 Testing

### Test Locally (Before Setting Up Railway Cron)

```bash
# Set environment variables
export PROD_DATABASE_URL="your_prod_database_url"
export DATABASE_URL="your_local_database_url"
export ENABLE_PROD_TO_LOCAL_MIGRATION="true"
export SOURCE_ATHLETE_ID="347085"
export TARGET_ATHLETE_ID="347085"

# Test the migration script directly
python scripts/migrate_athlete_155302.py

# Or test the scheduler wrapper
RUN_ONCE=true python src/scripts/daily_migration_scheduler.py
```

**Expected output:**
```
[MIGRATION SCHEDULER] Running in cron mode (run once)...
🚀 Running daily migration (cron mode)...
🔄 Starting production to local migration...
   [This may take 5-15 minutes depending on data size]
   Source athlete_id: 347085
   Target athlete_id: 347085
   [Calling scripts/migrate_athlete_155302.py...]
✅ Migration completed successfully
```

### Test in Railway

After adding the cron job, Railway will run it automatically. Check the logs:

1. Go to Railway Dashboard → **Logs** (top navigation)
2. Filter for cron job executions
3. Look for `[MIGRATION SCHEDULER]` messages
4. Verify it runs at 1 AM Central Time (7 AM UTC)

---

## 📋 Cron Schedule Reference

**Current Schedule:** `0 7 * * *`
- Format: `minute hour day month weekday`
- `0 7 * * *` = Every day at 07:00 UTC (1 AM CST)

**Other Options:**

| Time (Central) | Cron Schedule (UTC) | Notes |
|---------------|---------------------|-------|
| 1:00 AM CST | `0 7 * * *` | Current (winter) |
| 1:00 AM CDT | `0 6 * * *` | Summer time |
| 2:00 AM CST | `0 8 * * *` | Later option |
| 12:00 AM CST | `0 6 * * *` | Midnight CT |

---

## ⚠️ Important Notes

### Environment Variables

- **`ENABLE_PROD_TO_LOCAL_MIGRATION`** must be set to `"true"` (string) for the migration to run
- If not set or set to anything else, the migration will be skipped with a warning
- This allows you to enable/disable the migration without removing the cron job

### Safety

- The migration script uses upsert logic (insert or update) - it won't duplicate data
- It refreshes materialized views after migration
- If migration fails, it logs errors but doesn't crash the scheduler
- Migration has a 30-minute timeout to prevent hanging

### Local Development

- The migration is designed to run on Railway (cloud environment)
- For local testing, you can run it manually with `RUN_ONCE=true`
- Make sure your local machine has access to both production and local databases

---

## 🔧 Troubleshooting

### Migration Not Running

1. **Check environment variables:**
   - Verify `ENABLE_PROD_TO_LOCAL_MIGRATION=true` is set
   - Verify `PROD_DATABASE_URL` and `DATABASE_URL` are set

2. **Check Railway logs:**
   - Look for `[MIGRATION SCHEDULER]` messages
   - Check for error messages about missing environment variables

3. **Test locally:**
   - Run `RUN_ONCE=true python src/scripts/daily_migration_scheduler.py` locally
   - Check if it works without Railway

### Migration Failing

1. **Check database connectivity:**
   - Verify production database URL is accessible
   - Verify local database URL is correct

2. **Check athlete IDs:**
   - Verify `SOURCE_ATHLETE_ID` exists in production
   - Verify `TARGET_ATHLETE_ID` exists in local database (or run `setup_local_user_athlete.py` first)

3. **Check logs:**
   - Migration script outputs detailed logs
   - Look for specific error messages

### Migration Taking Too Long

- Migration has a 30-minute timeout
- If it consistently times out, consider:
  - Reducing the amount of data migrated
  - Running migration less frequently
  - Optimizing the migration script

---

## ✅ Done!

Your daily migration will now run automatically at 1 AM Central Time. You'll see execution logs in Railway's **Logs** view.
