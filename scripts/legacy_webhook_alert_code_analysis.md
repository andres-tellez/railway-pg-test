# Legacy Webhook Health Alert Code Analysis

## ✅ **CLEANUP COMPLETE**

All legacy webhook alert code has been deleted. This document is kept for reference only.

## Summary

This document identifies all code related to the legacy webhook health alert system that uses `ALERT_WEBHOOK_URL`.

## Files Involved

### 1. **`src/scripts/webhook_health_alert.py`** ⚠️ **LEGACY - Can Delete**
- **Purpose**: Main alert script that runs via cron job
- **Dependencies**:
  - Uses `check_webhook_health()` from `check_webhook_health.py`
  - Uses `ALERT_WEBHOOK_URL` environment variable
  - Uses `ALERT_EMAIL` environment variable (optional)
- **Functionality**:
  - Runs health check
  - Sends Discord/Slack alerts if unhealthy
  - Designed for daily cron execution
- **Status**: ⚠️ **Legacy** - Replaced by `/webhooks/strava/status` endpoint

### 2. **`src/scripts/check_webhook_health.py`** ⚠️ **POTENTIALLY LEGACY**
- **Purpose**: Health check function that queries webhook events table
- **Dependencies**: None (only uses database)
- **Functionality**:
  - Checks webhook event statistics
  - Reports recent failures
  - Identifies stuck events
  - Calculates success rates
- **Status**: ⚠️ **Check if used elsewhere** - If only used by alert script, can delete
- **Note**: The `/webhooks/strava/status` endpoint provides similar functionality

### 3. **Documentation Files** (Reference Only)
- `docs/webhook-alerting-setup.md` - Setup instructions for alert system
- `docs/webhook-production-activation.md` - Mentions alerting (lines 246, 294)

## Environment Variables Used

1. **`ALERT_WEBHOOK_URL`** - Discord/Slack webhook URL
2. **`ALERT_EMAIL`** - Email address (not implemented - TODO)

## Code Flow

```
Cron Job (Railway)
  ↓
webhook_health_alert.py
  ↓
check_webhook_health() → Database queries
  ↓
if unhealthy → send_alert() → Discord/Slack webhook
```

## Replacement

The legacy alert system is replaced by:
- **`/webhooks/strava/status`** endpoint (in `src/routes/webhook_routes.py`)
- Provides same health information via HTTP API
- Can be monitored manually or via external monitoring tools

## Recommendation

### If `check_webhook_health.py` is ONLY used by alert script:

**Delete these files:**
1. `src/scripts/webhook_health_alert.py`
2. `src/scripts/check_webhook_health.py`

**Delete these environment variables:**
1. `ALERT_WEBHOOK_URL`
2. `ALERT_EMAIL` (if exists)

**Update documentation:**
- Remove references from `docs/webhook-production-activation.md`
- Optionally keep `docs/webhook-alerting-setup.md` as historical reference (or delete)

### If `check_webhook_health.py` is used elsewhere:

**Keep:**
- `src/scripts/check_webhook_health.py` (if used by other scripts)

**Delete:**
- `src/scripts/webhook_health_alert.py` (alert wrapper only)
- `ALERT_WEBHOOK_URL` environment variable

## Next Steps

1. Verify if `check_webhook_health.py` is imported anywhere else
2. Check if cron job exists in Railway
3. If not used, delete the identified files
4. Remove environment variables from Railway
