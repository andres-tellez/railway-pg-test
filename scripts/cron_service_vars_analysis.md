# Cron Service Environment Variables Analysis

## What the Cron Service Actually Does

The `metrics_scheduler.py` runs three main tasks:
1. **Metrics refresh** - Refreshes materialized views (database only)
2. **Weekly plan rebuild** - Rebuilds training plans (database + OpenAI)
3. **Email notifications** - Sends weekly update emails (SendGrid/SMTP)

## Required Variables

### ✅ **Essential (Required)**

1. **`DATABASE_URL`** - ✅ **CRITICAL**
   - Used by: All services (database connection)
   - Location: `metrics_scheduler.py` line 538, 555, 580
   - Cannot run without it

### ✅ **Required for Weekly Rebuild**

2. **`OPENAI_API_KEY`** - ❌ **NOT REQUIRED**
   - **Note**: Weekly rebuild uses deterministic pipeline (no LLM)
   - From README: "Layer 3 & 4: Removed (LLM-based). This project now uses a fully deterministic pipeline"
   - Weekly rebuild does NOT call OpenAI/GPT

3. **`OPENAI_MODEL`** / **`OPENAI_TRAINING_PLAN_MODEL`** - ❌ **NOT REQUIRED**
   - Not used by weekly rebuild (deterministic pipeline)

### ✅ **Required for Email Notifications**

4. **`SENDGRID_API_KEY`** - ✅ **REQUIRED** (preferred)
   - Used by: `EmailService.send_weekly_update_email()`
   - Alternative: SMTP variables (but SendGrid REST API preferred)

5. **`SENDGRID_FROM_EMAIL`** - ✅ **REQUIRED**
   - Used by: Email sender address

6. **`SENDGRID_FROM_NAME`** - ✅ **REQUIRED**
   - Used by: Email sender name

   **OR** (if using SMTP instead):
   - `SMTP_HOST`
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `SMTP_PORT`
   - `SMTP_FROM_EMAIL`
   - `SMTP_FROM_NAME`

## Optional Variables

### ⚠️ **Optional (Not Required)**

1. **`USE_UTC_TIME`** - ⚠️ **Optional**
   - Used by: `get_current_local_time()` function
   - Default: `false` (uses Central Time)
   - Only needed if you want UTC timezone

2. **`RUN_ONCE`** - ⚠️ **Optional**
   - Used by: Cron mode (run once vs. long-running worker)
   - Default: `false` (long-running worker mode)
   - Set to `true` for Railway cron jobs

## NOT Needed Variables

### ❌ **Not Required by Cron Service**

These variables are used by the backend web service, but **NOT** by the cron service:

1. **`AUTH0_*`** - ❌ Not needed (cron doesn't authenticate users)
2. **`CORS_ORIGINS`** - ❌ Not needed (cron doesn't serve HTTP requests)
3. **`STRAVA_CLIENT_ID`** - ❌ Not needed (cron doesn't make Strava API calls)
4. **`STRAVA_CLIENT_SECRET`** - ❌ Not needed (cron doesn't make Strava API calls)
5. **`STRAVA_REDIRECT_URI`** - ❌ Not needed (cron doesn't handle OAuth)
6. **`FRONTEND_REDIRECT`** - ❌ Not needed (cron doesn't redirect users)
7. **`SESSION_COOKIE_*`** - ❌ Not needed (cron doesn't manage sessions)
8. **`ALERT_WEBHOOK_URL`** - ❌ Not needed (legacy, deleted)
9. **`CRON_SECRET_KEY`** - ❌ Not needed (legacy, deleted)
10. **`INTERNAL_API_KEY`** - ❌ Not needed (legacy, deleted)
11. **`ACCESS_TOKEN_EXP`** - ❌ Not needed (cron doesn't manage tokens)
12. **`AUTH_BYPASS`** - ❌ Not needed (cron doesn't authenticate)
13. **`AUTH0_ISSUER_URL`** - ❌ Not needed (duplicate of AUTH0_ISSUER)

## Summary

### Minimal Required Variables for Cron Service:

```bash
# Essential (Required)
DATABASE_URL=postgresql://...

# For email notifications (Required)
SENDGRID_API_KEY=SG....
SENDGRID_FROM_EMAIL=your-email@example.com
SENDGRID_FROM_NAME=SmartCoach

# Optional
USE_UTC_TIME=false
RUN_ONCE=true  # Set to true for Railway cron mode
```

### Current Status

Looking at your Railway dashboard, the cron service has **33 variables**, but it only actually needs **~5-6 variables** (DATABASE_URL + SendGrid vars + optional USE_UTC_TIME/RUN_ONCE).

**Most variables are unnecessary** and can be removed to simplify the configuration.
