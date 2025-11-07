# How to Check if Webhooks Are Active

## Quick Check Methods

### Method 1: Check Subscription Status (Easiest)

Run this command to see if there's an active webhook subscription:

```bash
python -m src.scripts.manage_webhook_subscription view
```

**Results:**
- ✅ **If subscription exists:** You'll see subscription ID, callback URL, and creation date → **Webhooks ARE active**
- ❌ **If no subscription:** Message says "No active webhook subscriptions found" → **Webhooks are NOT active**

### Method 2: Check Webhook Status Endpoint

Visit or curl this URL:

```bash
# For staging
curl https://api.smartcoach.dev/webhooks/strava/status

# For production (if different)
curl https://api.smartcoach.dev/webhooks/strava/status
```

**Results:**
- ✅ **If webhooks are active:** You'll see `"stats"` with event counts (completed, pending, failed)
- ❌ **If no events:** Stats will be empty `{}` → **May or may not be active** (need to check subscription)

### Method 3: Check Database for Webhook Events

Run this SQL query:

```sql
-- Check if webhook_events table exists and has data
SELECT COUNT(*) as total_events,
       COUNT(*) FILTER (WHERE status = 'completed') as completed,
       MAX(received_at) as last_event
FROM webhook_events;
```

**Results:**
- ✅ **If events exist:** You're receiving webhooks → **Webhooks ARE active**
- ❌ **If table is empty:** No events received → **Webhooks may not be active** (or just no activities yet)

### Method 4: Check Railway Logs

Look for these log patterns in Railway:

**Active webhooks:**
```
📬 Webhook received: activity.create (object_id=123456, owner_id=789)
✅ Webhook event stored: ID=1
✅ Event processed successfully
```

**No webhooks:**
- No webhook-related logs
- Only cron job or manual sync logs

## Decision Tree

```
1. Run: python -m src.scripts.manage_webhook_subscription view
   │
   ├─→ Subscription exists?
   │   │
   │   ├─→ YES → ✅ Webhooks ARE active (keep STRAVA_WEBHOOK_VERIFY_TOKEN)
   │   │
   │   └─→ NO → Check database for events
   │       │
   │       ├─→ Events exist?
   │       │   │
   │       │   ├─→ YES → ✅ Webhooks were active (may have been deleted)
   │       │   │
   │       │   └─→ NO → ❌ Webhooks are NOT active (can remove token)
   │
   └─→ Error connecting to Strava?
       → Check STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET
```

## Quick Test

**Fastest way to check:**

1. **Check subscription:**
   ```bash
   python -m src.scripts.manage_webhook_subscription view
   ```

2. **If subscription exists** → Keep `STRAVA_WEBHOOK_VERIFY_TOKEN`
3. **If no subscription** → You can remove `STRAVA_WEBHOOK_VERIFY_TOKEN` (but you'll need it if you enable webhooks later)

## What Each Method Tells You

| Method | What It Checks | Reliability |
|--------|----------------|-------------|
| **View subscription** | Active subscription in Strava | ✅ Most reliable |
| **Status endpoint** | Events received by app | ⚠️ May be empty if no activities |
| **Database check** | Historical events received | ⚠️ May be empty if no activities |
| **Railway logs** | Recent webhook activity | ⚠️ Only shows recent activity |

## Recommendation

**Use Method 1 (view subscription)** - It's the most reliable way to check if webhooks are actually configured and active.
