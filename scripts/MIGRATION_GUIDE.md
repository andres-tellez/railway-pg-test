# Production to Local Data Migration Guide

This guide explains how to copy data from your production environment (main Strava account) to your local environment (test Strava account) for development purposes.

## Overview

The migration script (`migrate_prod_to_local.py`) copies all Strava-related data from production to local and automatically updates all IDs to work with your local test account.

## Prerequisites

1. **Production Database Access**: You need the production database URL
2. **Local Database Access**: Your local database must be accessible
3. **Test Account Connected**: Your local environment must have a test Strava account already connected (this creates the user_id and athlete_id mappings)

## Setup

### Step 1: Prepare Environment Variables

Create a `.env.prod` file in the project root with your production database URL:

```bash
PROD_DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require
```

Your `.env.local` should already have your local database URL:

```bash
DATABASE_URL=postgresql://user:password@localhost:port/database
```

### Step 2: Ensure Test Account is Connected

Before running the migration, make sure your local environment has the test Strava account connected:

1. Start your local application
2. Log in with your test Strava account
3. Complete the OAuth flow to connect the account
4. Verify the account is connected (check `user_athletes` table)

This ensures the local database has the `user_id` and `athlete_id` that will be used for the migrated data.

## Running the Migration

### Option 1: Using the Script Directly

```bash
python scripts/migrate_prod_to_local.py
```

The script will:
1. Connect to both production and local databases
2. Identify the production user/athlete IDs (main account)
3. Identify the local user/athlete IDs (test account)
4. Copy all data and remap IDs accordingly
5. Show progress and any errors

### Option 2: Using PowerShell (Windows)

```powershell
cd C:\Users\andre\projects\railway-pg-test
python scripts/migrate_prod_to_local.py
```

## What Gets Migrated

The script migrates the following tables in order:

1. **user_identity** - User account information (with user_id mapping)
2. **user_athletes** - Athlete linking (with athlete_id mapping)
3. **user_profile** - User profile data
4. **activities** - All Strava activities (with athlete_id and user_id mapping)
5. **splits** - Activity splits (activity_id stays the same - Strava's global ID)
6. **plans** - Training plans (with user_id mapping, new plan_id generated, preserves is_active status)
7. **plan_workouts** - Plan workout details (with plan_id mapping)
8. **weekly_metrics** - Weekly performance metrics (with plan_id mapping)
9. **weekly_decision_log** - Weekly decision logs (with plan_id mapping)
10. **strava_sync_status** - Sync status/progress (with user_id and athlete_id mapping) - **For UX consistency**
11. **conversations** - User conversations (with user_id mapping, new conversation_id)

## ID Mapping Strategy

### IDs That Are Mapped

- **user_id**: Production user_id → Local test account user_id
- **athlete_id**: Production athlete_id → Local test account athlete_id
- **plan_id**: Production plan_id → New auto-increment plan_id
- **conversation_id**: Production conversation_id → New UUID

### IDs That Stay the Same

- **activity_id**: Strava's global activity IDs remain unchanged
- **split.id**: Auto-increment, but references activity_id which stays the same

### IDs That Are NOT Migrated

- **tokens**: Strava tokens are NOT migrated (they won't work with test account)
  - You'll need to re-authenticate with Strava in local environment

## Important Notes

### ⚠️ Tokens

Strava tokens are **NOT** migrated because:
- They're encrypted and tied to the production athlete_id
- They won't work with the test account anyway
- You'll need to re-authenticate with Strava in your local environment

### ⚠️ Activity IDs

Strava activity IDs are global and remain the same. This means:
- Activities copied from production will have the same activity_id
- If you already have activities in local with the same IDs, they'll be updated
- This is intentional - Strava IDs are global identifiers

### ✅ Active Plans

Plans maintain their `is_active` status from production:
- If a plan was active in production, it will be active in local
- This ensures your "current plan" shows up correctly in the UI
- You can still manually activate/deactivate plans after migration if needed

### ⚠️ Data Conflicts

The script uses upsert logic (INSERT ... ON CONFLICT UPDATE) for most tables:
- If data already exists, it will be updated
- If data doesn't exist, it will be inserted
- This allows you to re-run the migration safely

## Troubleshooting

### Error: "No local user found"

**Solution**: Make sure your test Strava account is connected in the local environment first.

1. Start your local app
2. Log in with test account
3. Complete OAuth flow
4. Verify in database: `SELECT * FROM user_athletes;`

### Error: "No production user found"

**Solution**: Check that your production database URL is correct and accessible.

### Error: Foreign Key Constraint Violation

**Solution**: The script migrates tables in dependency order. If you see FK errors:
1. Check that previous steps completed successfully
2. Verify the local database schema matches production
3. Run migrations if needed: `alembic upgrade head`

### Error: Connection Refused

**Solution**:
- Verify database URLs are correct
- Check network connectivity
- Ensure databases are accessible from your machine
- For Railway databases, check proxy settings

## Verification

After migration, verify the data:

```sql
-- Check activities count
SELECT COUNT(*) FROM activities;

-- Check plans
SELECT COUNT(*) FROM plans;

-- Check user mapping
SELECT * FROM user_athletes;

-- Check a sample activity
SELECT activity_id, name, start_date, distance
FROM activities
ORDER BY start_date DESC
LIMIT 5;
```

## Re-running Migration

You can safely re-run the migration script:
- Existing data will be updated
- New data will be inserted
- ID mappings are recreated each time

## Best Practices

1. **Backup First**: Always backup your local database before migration
2. **Test Account**: Use a dedicated test Strava account (not your main account)
3. **Incremental Updates**: Re-run migration periodically to sync new data
4. **Verify After**: Always verify key data after migration

## Example Workflow

```bash
# 1. Backup local database (optional but recommended)
pg_dump $LOCAL_DATABASE_URL > local_backup.sql

# 2. Ensure test account is connected
# (Start app, log in, complete OAuth)

# 3. Run migration
python scripts/migrate_prod_to_local.py

# 4. Verify data
psql $LOCAL_DATABASE_URL -c "SELECT COUNT(*) FROM activities;"

# 5. Test your application
# (Start app, verify activities show up, test features)
```

## Support

If you encounter issues:
1. Check the error messages - they're usually descriptive
2. Verify database connectivity
3. Ensure test account is connected
4. Check that all migrations are up to date
