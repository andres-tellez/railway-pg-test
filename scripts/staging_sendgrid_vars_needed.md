# SendGrid Variables Needed for Staging Cron Service

## Summary

Based on code analysis, **SendGrid REST API** is the preferred email method (SMTP doesn't work on Railway). The cron service (`metrics_scheduler.py`) sends weekly update emails to users, so these variables need to be in the **Cron Service** environment, not the backend web service.

## Required Variables to Add

### 1. `SENDGRID_API_KEY` ⭐ **CRITICAL**
- **Value**: Your SendGrid API key (starts with `SG.`)
- **Reason**: This is the primary method - Railway blocks SMTP ports
- **Code location**: `src/services/email_service.py` line 54
- **Priority**: **REQUIRED** for staging/production

### 2. `SENDGRID_FROM_EMAIL` (or use existing `SMTP_FROM_EMAIL`)
- **Value**: Your sender email (e.g., `andrestellez@outlook.com`)
- **Reason**: Required for SendGrid API to send emails
- **Code location**: `src/services/email_service.py` line 55
- **Priority**: **REQUIRED** if using `SENDGRID_API_KEY`
- **Note**: Can reuse existing `SMTP_FROM_EMAIL` value

### 3. `SENDGRID_FROM_NAME` (or use existing `SMTP_FROM_NAME`)
- **Value**: Your sender name (e.g., `SmartCoach`)
- **Reason**: Display name for sent emails
- **Code location**: `src/services/email_service.py` line 56-57
- **Priority**: **OPTIONAL** (defaults to "SmartCoach" if not set)
- **Note**: Can reuse existing `SMTP_FROM_NAME` value

## How Email Service Works

The code tries methods in this order:

1. **SendGrid REST API** (preferred) - if `SENDGRID_API_KEY` is set
2. **SMTP fallback** - only if `SENDGRID_API_KEY` is NOT set

**Important**: If `SENDGRID_API_KEY` is set, SMTP variables are **ignored**.

## Current Staging Status

**Cron Service:**
- ❌ **Missing**: `SENDGRID_API_KEY`
- ❌ **Missing**: `SENDGRID_FROM_EMAIL` (or `SMTP_FROM_EMAIL`)
- ❌ **Missing**: `SENDGRID_FROM_NAME` (or `SMTP_FROM_NAME`)

**Backend Service** (if you have SMTP vars there):
- ✅ **Has**: `SMTP_FROM_EMAIL` (can reference same value)
- ✅ **Has**: `SMTP_FROM_NAME` (can reference same value)
- ✅ **Has**: `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_PORT` (not needed if using REST API)

## Action Items

1. **Add to Railway staging Cron Service** (not backend web service):
   ```
   SENDGRID_API_KEY=SG.your_actual_api_key_here
   SENDGRID_FROM_EMAIL=andrestellez@outlook.com
   SENDGRID_FROM_NAME=SmartCoach
   ```

   **Note**: The cron service runs `metrics_scheduler.py` which sends weekly update emails to users.

2. **Optional - Remove SMTP variables** (if you want to clean up):
   - `SMTP_HOST`
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `SMTP_PORT`

   **Note**: Keep `SMTP_FROM_EMAIL` and `SMTP_FROM_NAME` as fallback if `SENDGRID_FROM_EMAIL`/`SENDGRID_FROM_NAME` are not set.

## Code Evidence

### Email Service (used by cron scheduler)

From `src/services/email_service.py`:

```python
# Line 309-314: Tries SendGrid REST API first
# Try SendGrid API first (preferred - works on Railway)
sendgrid_config = EmailService.get_sendgrid_config()
if sendgrid_config["api_key"]:
    return EmailService.send_email_via_sendgrid_api(...)

# Line 316-323: Only falls back to SMTP if API key not set
# Fallback to SMTP (may not work on Railway)
if SMTP_AVAILABLE:
    logger.warning(
        "⚠️  Using SMTP fallback. SendGrid API is recommended for Railway (set SENDGRID_API_KEY)"
    )
```

### Cron Service Usage

From `src/scripts/metrics_scheduler.py`:
- Line 9: "3. Email notifications - sends weekly update emails to users with changes"
- Line 314: `from src.services.email_service import EmailService`
- Line 448: `EmailService.send_weekly_update_email(...)`

The cron service runs weekly and sends email notifications to users about their training plan updates.

## Validation

After adding these variables, run:
```bash
python scripts/validate_env_capabilities.py
```

You should see:
```
✅ Email Service Config: SendGrid REST API configured (preferred - works on Railway)
```
