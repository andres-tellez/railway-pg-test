# Diagnosing Missing Activity Data

## Quick Start

### Option 1: Python Diagnostic Script (Recommended)

Run the diagnostic script with your email or athlete_id:

```bash
# Using email
python diagnose_missing_activity.py your.email@example.com

# Using athlete_id
python diagnose_missing_activity.py 347085

# Using both
python diagnose_missing_activity.py 347085 your.email@example.com
```

The script will check:
1. ✅ Recent webhook events (last 24 hours)
2. ✅ User-athlete linkage
3. ✅ Strava token status
4. ✅ Recent activities in database
5. ✅ Sync status history

### Option 2: Direct SQL Queries

Use the queries in `diagnose_missing_activity_queries.sql`:

1. Connect to your production database
2. Replace `<athlete_id>` and `<user_email>` with your values
3. Run each query to check different aspects

## Common Issues & Solutions

### ❌ No Webhook Events Received
**Symptoms:** No rows in `webhook_events` table
**Causes:**
- Webhook subscription not active in Strava Developer Portal
- Webhook endpoint not accessible (firewall/network)
- Strava didn't send webhook (rare)

**Solution:**
1. Check Strava Developer Portal → Webhooks
2. Verify webhook URL is correct and accessible
3. Test webhook subscription status

### ❌ Webhook Event Failed
**Symptoms:** `status = 'FAILED'` in `webhook_events` table
**Check:** Look at `error_message` column

**Common errors:**
- `"No user-athlete link found"` → Reconnect Strava account
- `"No valid token for athlete"` → Token expired/revoked, reconnect Strava
- `"Failed to fetch activity"` → Strava API issue or activity deleted

### ❌ Missing User-Athlete Link
**Symptoms:** No row in `user_athletes` table
**Solution:** Reconnect Strava account via OAuth flow

### ❌ Token Expired/Revoked
**Symptoms:** Token `expires_at` in past or `revoked_at` set
**Solution:** Reconnect Strava account via OAuth flow

### ⚠️ Activity Not Enriched
**Symptoms:** Activity exists but missing HR zones/metrics
**Solution:**
```bash
# Manual enrichment
POST /api/activities/enrich/activity/<activity_id>
```

## Manual Recovery Steps

If you find the issue, here's how to recover:

### 1. Reconnect Strava (if token/link issue)
- Go to Settings → Disconnect Strava
- Reconnect Strava account
- This will trigger automatic sync

### 2. Manual Activity Fetch
```bash
# Fetch specific activity
POST /admin/fetch-activity/<activity_id>?athlete_id=<athlete_id>
```

### 3. Manual Sync Trigger
```bash
# Sync last 7 days
POST /admin/trigger-ingest/<athlete_id>?lookback_days=7&max_activities=50
```

## Getting Your Activity ID from Strava

1. Go to Strava.com → Your Activity
2. Look at the URL: `https://www.strava.com/activities/1234567890`
3. The number at the end is your `activity_id`

## Next Steps After Diagnosis

1. **If webhook failed:** Check error message, fix root cause, then manually fetch activity
2. **If no webhook received:** Check webhook subscription, then manually sync
3. **If token expired:** Reconnect Strava account
4. **If activity exists but not enriched:** Run enrichment endpoint

## Need Help?

Check the diagnostic script output - it provides specific recommendations based on what it finds.
