# Production Webhook Subscription Activation Guide

**Purpose:** Activate Strava webhook subscription for production environment
**Status:** ⬜ Not Started / ⬜ In Progress / ⬜ Active / ⬜ Verified

---

## Prerequisites

Before activating the production webhook, ensure:

- [x] Webhook infrastructure is implemented (`src/routes/webhook_routes.py`)
- [x] Webhook processor is implemented (`src/services/webhook_processor.py`)
- [x] Database models exist (`src/db/models/webhook_events.py`)
- [x] Management script is ready (`src/scripts/manage_webhook_subscription.py`)
- [ ] Production environment is deployed and accessible
- [ ] Environment variables are configured in Railway

---

## Step 1: Configure Environment Variables

Set these in your **production Railway environment**:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `STRAVA_CLIENT_ID` | Your Strava app client ID | `155302` |
| `STRAVA_CLIENT_SECRET` | Your Strava app client secret | `...` |
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | Secret token for webhook verification | `your-secret-token-here` |
| `WEBHOOK_CALLBACK_URL` | Your public webhook endpoint URL | `https://api.smartcoach.dev/webhooks/strava` |

### Verify Configuration

1. Go to Railway dashboard → Your production service
2. Navigate to "Variables" tab
3. Verify all 4 variables are set
4. **Important:** `WEBHOOK_CALLBACK_URL` must be the **production** URL:
   - ✅ Production: `https://api.smartcoach.dev/webhooks/strava`
   - ❌ Not: `https://localhost:5000/webhooks/strava`

---

## Step 2: Verify Webhook Endpoint is Accessible

### Test Webhook Verification Endpoint

The webhook verification endpoint should be publicly accessible:

**URL:** `https://api.smartcoach.dev/webhooks/strava`

**Test with curl:**
```bash
curl "https://api.smartcoach.dev/webhooks/strava?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=YOUR_VERIFY_TOKEN"
```

**Expected Response:**
```json
{"hub.challenge": "test123"}
```

**Status Code:** `200 OK`

If this fails:
- Check that Railway service is running
- Verify the endpoint route is registered in `src/app.py`
- Check Railway logs for errors

---

## Step 3: Activate Webhook Subscription

### Option A: Using the Management Script (Recommended)

**Run from your local machine** (with production environment variables):

```bash
# View current subscriptions (if any)
python -m src.scripts.manage_webhook_subscription view

# Create production subscription
python -m src.scripts.manage_webhook_subscription create
```

**Or via Railway CLI:**
```bash
# SSH into Railway service
railway shell

# Run the script
python -m src.scripts.manage_webhook_subscription create
```

### Option B: Manual API Call

If the script doesn't work, create subscription manually:

```bash
curl -X POST https://www.strava.com/api/v3/push_subscriptions \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "callback_url=https://api.smartcoach.dev/webhooks/strava" \
  -d "verify_token=YOUR_VERIFY_TOKEN"
```

**Expected Response:**
```json
{
  "id": 12345,
  "callback_url": "https://api.smartcoach.dev/webhooks/strava",
  "created_at": "2025-11-03T12:00:00Z"
}
```

**Save the subscription ID** - you'll need it to delete/modify later.

---

## Step 4: Verify Webhook Subscription

### Check Subscription Status

```bash
python -m src.scripts.manage_webhook_subscription view
```

**Expected Output:**
```
✅ Found 1 subscription(s):

   ID: 12345
   Callback URL: https://api.smartcoach.dev/webhooks/strava
   Created: 2025-11-03T12:00:00Z
```

### Test Webhook Reception

1. **Record a test activity in Strava:**
   - Open Strava app on your phone
   - Record a short run/walk
   - Save the activity

2. **Check webhook status endpoint:**
   - Visit: `https://api.smartcoach.dev/webhooks/strava/status`

3. **Verify in database:**
   ```sql
   SELECT * FROM webhook_events
   ORDER BY received_at DESC
   LIMIT 10;
   ```

4. **Check Railway logs:**
   - Look for: `📬 Webhook received: activity.create`
   - Verify: `✅ Webhook event stored: ID=...`

---

## Step 5: Verify Activity Sync

After webhook is activated, verify activities are syncing:

1. **Check webhook status:**
   - Visit: `https://api.smartcoach.dev/webhooks/strava/status`
   - Or check database directly

2. **Verify activity appears in database:**
   ```sql
   SELECT activity_id, name, start_date, distance
   FROM activities
   WHERE athlete_id = YOUR_ATHLETE_ID
   ORDER BY start_date DESC
   LIMIT 5;
   ```

3. **Check metrics page:**
   - Visit: `https://app.smartcoach.dev/metrics`
   - Verify new activity appears in metrics

---

## Troubleshooting

### Issue: Webhook verification fails

**Symptoms:** Subscription creation fails with 403 or timeout

**Solutions:**
1. Verify `STRAVA_WEBHOOK_VERIFY_TOKEN` matches in Railway and script
2. Check webhook endpoint is publicly accessible (not behind VPN/firewall)
3. Verify endpoint returns 200 OK for GET requests
4. Check Railway logs for verification attempts

### Issue: Webhooks not being received

**Symptoms:** No webhook events in database after recording activity

**Solutions:**
1. Verify subscription is active: `python -m src.scripts.manage_webhook_subscription view`
2. Check Railway logs for incoming POST requests
3. Verify webhook endpoint is responding with 200 OK
4. Check Strava Developer Portal for webhook delivery status (if available)

### Issue: Webhook processing fails

**Symptoms:** Events received but status is FAILED

**Solutions:**
1. Check Railway logs for error messages
2. Verify athlete has valid access token
3. Check database for error messages: `SELECT error_message FROM webhook_events WHERE status = 'FAILED'`
4. Run retry script: `python -m src.scripts.retry_failed_webhooks` (if exists)

---

## Monitoring & Maintenance

### Daily Health Check

Monitor webhook health via HTTP endpoint:

**URL:** `https://api.smartcoach.dev/webhooks/strava/status`

**Response includes:**
- Event counts by status
- Recent events
- Processing statistics

You can also check the database directly:
```sql
SELECT status, COUNT(*)
FROM webhook_events
GROUP BY status;
```

---

## Production Checklist

Before marking this task complete:

- [ ] Environment variables configured in Railway production
- [ ] Webhook endpoint is publicly accessible and responding
- [ ] Webhook subscription created successfully
- [ ] Subscription verified via `view` command
- [ ] Test activity recorded and webhook received
- [ ] Activity synced to database
- [ ] Webhook health check passes
- [ ] Monitoring/alerting configured (optional)

---

## Related Documentation

- [Webhook Setup Guide](./webhook-setup-guide.md) - Complete setup instructions
- [Webhook Deployment Checklist](./webhook-deployment-checklist.md) - Deployment checklist
- [Webhook Routes](../src/routes/webhook_routes.py) - Implementation code
- [Webhook Processor](../src/services/webhook_processor.py) - Processing logic
- [Manage Webhook Script](../src/scripts/manage_webhook_subscription.py) - Management tool

---

## Quick Reference Commands

```bash
# View subscription
python -m src.scripts.manage_webhook_subscription view

# Create subscription
python -m src.scripts.manage_webhook_subscription create

# Delete subscription
python -m src.scripts.manage_webhook_subscription delete <subscription_id>

# Check health (via API endpoint)
curl https://api.smartcoach.dev/webhooks/strava/status
```

---

**Last Updated:** November 3, 2025
