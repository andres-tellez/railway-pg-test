# Strava Webhooks Setup Guide

Complete guide to setting up real-time Strava activity syncing using webhooks.

## 🎯 What Are Webhooks?

Instead of polling Strava every 6 hours for new activities, webhooks allow Strava to **push** notifications to your app instantly when:
- A user creates a new activity ✅ (primary use case)
- A user updates an activity
- A user deletes an activity

## 📋 Prerequisites

1. **Railway deployment** (or any public HTTPS endpoint)
2. **Strava API credentials** (client ID & secret)
3. **Database** (PostgreSQL) for storing webhook events

## 🔧 Setup Steps

### Step 1: Add Environment Variables

Add these to your Railway environment (or `.env.staging`):

```bash
# Webhook Configuration
STRAVA_WEBHOOK_VERIFY_TOKEN=your_secret_random_token_here_min_32_chars
WEBHOOK_CALLBACK_URL=https://your-app.up.railway.app/webhooks/strava

# Existing Strava Variables (you should already have these)
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

**How to generate a secure verify token:**
```bash
# On Linux/Mac
openssl rand -hex 32

# Or use Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Or manually create a long random string (minimum 32 characters)
```

### Step 2: Run Database Migration

```bash
# From project root
alembic upgrade head
```

This creates the `webhook_events` table to store incoming notifications.

### Step 3: Deploy to Railway

```bash
git add .
git commit -m "Add Strava webhook support"
git push origin staging
```

Wait for Railway to deploy (~2-3 minutes).

### Step 4: Register Webhook with Strava

Once deployed, register your webhook endpoint:

```bash
python -m src.scripts.manage_webhook_subscription create
```

This will:
1. Contact Strava's API
2. Strava sends a verification challenge to your endpoint
3. Your endpoint responds correctly
4. Webhook subscription is activated!

### Step 5: Verify It's Working

**Test the endpoint manually:**
```bash
curl https://your-app.up.railway.app/webhooks/strava/status
```

**Check webhook events:**
```sql
SELECT * FROM webhook_events ORDER BY received_at DESC LIMIT 10;
```

**Test with a real activity:**
1. Open Strava mobile app
2. Record a short run (even 1 minute)
3. Save it
4. Within 30 seconds, check your database:
```sql
SELECT * FROM webhook_events ORDER BY received_at DESC LIMIT 1;
SELECT * FROM activities ORDER BY created_at DESC LIMIT 1;
```

## 🔍 Monitoring & Debugging

### View Webhook Status

```bash
# Check current subscription
python -m src.scripts.manage_webhook_subscription view
```

### Check Recent Events

```sql
-- All events
SELECT * FROM webhook_events ORDER BY received_at DESC;

-- Failed events
SELECT * FROM webhook_events WHERE status = 'failed';

-- Events by type
SELECT object_type, aspect_type, COUNT(*)
FROM webhook_events
GROUP BY object_type, aspect_type;
```

### Railway Logs

Check Railway logs for webhook processing:
```
https://railway.app/project/[your-project]/deployments
```

Look for:
- `📬 Webhook received` - Event came in
- `✅ Webhook event stored` - Saved to database
- `✅ Event processed successfully` - Activity fetched and stored

## 🐛 Troubleshooting

### Problem: Verification Failed

**Symptoms:**
```
❌ Webhook verification failed - invalid token
```

**Solutions:**
1. Check `STRAVA_WEBHOOK_VERIFY_TOKEN` is set correctly
2. Verify Railway deployment has the env var
3. Try restarting the Railway deployment

### Problem: No Events Received

**Symptoms:** Record activity, but no rows in `webhook_events`

**Solutions:**
1. Check subscription is active:
   ```bash
   python -m src.scripts.manage_webhook_subscription view
   ```
2. Verify callback URL is correct (must be public HTTPS)
3. Check Railway logs for incoming requests
4. Test endpoint manually:
   ```bash
   curl https://your-app.up.railway.app/webhooks/strava
   ```

### Problem: Events Stuck in "pending" Status

**Symptoms:** Events in database but `status = 'pending'`

**Solutions:**
1. Check Railway logs for processing errors
2. Verify athlete has valid Strava token
3. Check Strava API rate limits
4. Manually retry failed events:
   ```sql
   UPDATE webhook_events
   SET status = 'pending', retry_count = 0
   WHERE status = 'failed';
   ```

### Problem: Activity Not Showing Up

**Symptoms:** Webhook event processed, but activity not in database

**Solutions:**
1. Check if activity is a "Run" (we only sync runs)
2. Verify user has valid Strava connection
3. Check for errors in `webhook_events.error_message`
4. Look at Railway logs for "Failed to fetch activity"

## 🔄 Managing Subscriptions

### View Current Subscription
```bash
python -m src.scripts.manage_webhook_subscription view
```

### Delete Subscription
```bash
python -m src.scripts.manage_webhook_subscription delete <subscription_id>
```

### Recreate Subscription
```bash
# Delete old one
python -m src.scripts.manage_webhook_subscription delete <id>

# Create new one
python -m src.scripts.manage_webhook_subscription create
```

## 📊 Performance

**Benefits over cron polling:**
- **Instant sync:** Activities appear within 30 seconds
- **95% fewer API calls:** Only fetch when there's actually a new activity
- **Scales infinitely:** Same infrastructure works for 10 or 10,000 users
- **No rate limits:** Not making thousands of unnecessary requests

**Infrastructure:**
- **Zero extra cost:** Uses existing Railway deployment
- **Fast responses:** Events stored immediately, processed in background
- **Fault-tolerant:** Failed events can be retried automatically

## 🔐 Security

**How webhooks are secured:**
1. **Verification token:** Strava must know your secret token
2. **HTTPS required:** All communication encrypted
3. **Event validation:** We verify all required fields are present
4. **Deduplication:** Database prevents duplicate processing
5. **Error handling:** Failed events don't crash the system

## 📚 References

- [Strava Webhook Events API](https://developers.strava.com/docs/webhooks/)
- [Event Subscriptions](https://developers.strava.com/docs/webhookexample/)
- [Webhook Event Types](https://developers.strava.com/docs/webhookeventtypes/)

## ✅ Success Checklist

- [ ] Environment variables configured in Railway
- [ ] Database migration applied
- [ ] Code deployed to Railway
- [ ] Webhook subscription created successfully
- [ ] Test activity synced within 30 seconds
- [ ] Monitoring dashboard shows events
- [ ] No errors in Railway logs
- [ ] Cron job disabled (optional - keep as backup)

## 🎉 You're Done!

Your app now receives **real-time activity notifications** from Strava!

Users will see their activities appear almost instantly after they finish recording them.

**Next steps:**
- Monitor the webhook status endpoint regularly
- Set up alerts for failed events (optional)
- Consider implementing activity.update events for edit sync
- Keep the cron job as a backup safety net (runs once daily)
