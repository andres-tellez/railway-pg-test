# 🚀 Webhook Deployment Checklist

Quick reference for deploying Strava webhooks to production.

## 📝 Pre-Deployment Checklist

### 1. Environment Variables

Add these to Railway environment:

```bash
# Required - generate a random 32+ character string
STRAVA_WEBHOOK_VERIFY_TOKEN=your_secret_token_here

# Required - your public webhook endpoint
WEBHOOK_CALLBACK_URL=https://your-app.up.railway.app/webhooks/strava

# Should already exist
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
DATABASE_URL=postgresql://...
```

### 2. Database Migration

```bash
# Run this locally first to test
alembic upgrade head

# Or on Railway, migration will run automatically on deploy
```

### 3. Code Changes

- [x] `src/db/models/webhook_events.py` - Database model
- [x] `src/routes/webhook_routes.py` - Webhook endpoints
- [x] `src/services/webhook_processor.py` - Event processing logic
- [x] `src/scripts/manage_webhook_subscription.py` - Management script
- [x] `src/app.py` - Register webhook blueprint
- [x] `src/db/models/__init__.py` - Export WebhookEvent model
- [x] `alembic/versions/f001_*.py` - Database migration

## 🚢 Deployment Steps

### Step 1: Commit & Push

```bash
git status
git add .
git commit -m "Add Strava webhook real-time sync"
git push origin development
```

### Step 2: Merge to Staging

```bash
git checkout staging
git merge development
git push origin staging
```

### Step 3: Wait for Railway Deployment

Monitor at: https://railway.app/project/[your-project]/deployments

Look for:
- ✅ Build successful
- ✅ Deploy successful
- ✅ Health check passing

### Step 4: Verify Deployment

```bash
# Test health endpoint
curl https://your-app.up.railway.app/health

# Test webhook status endpoint
curl https://your-app.up.railway.app/webhooks/strava/status
```

### Step 5: Register Webhook with Strava

```bash
# Make sure environment variables are set first
python -m src.scripts.manage_webhook_subscription create
```

Expected output:
```
✅ Webhook subscription created successfully!
   Subscription ID: 123456
   Callback URL: https://your-app.up.railway.app/webhooks/strava
```

### Step 6: Test with Real Activity

1. Open Strava mobile app
2. Record a short run (1-2 minutes)
3. Complete and save the activity
4. Wait 30 seconds
5. Check webhook status:

```bash
curl https://your-app.up.railway.app/webhooks/strava/status
```

Should show:
```json
{
  "status": "ok",
  "stats": {
    "pending": 0,
    "completed": 1
  },
  "recent_events": [...]
}
```

## ✅ Verification Checklist

After deployment, verify:

- [ ] Railway deployment successful
- [ ] Environment variables loaded (check Railway dashboard)
- [ ] Database migration applied (check `alembic_version` table)
- [ ] Webhook endpoint accessible (`/webhooks/strava/status`)
- [ ] Subscription created successfully
- [ ] Test activity synced within 30 seconds
- [ ] Activity appears in database
- [ ] No errors in Railway logs

## 🔧 Configuration Reference

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | ✅ Yes | Secret token for webhook verification | `d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9` |
| `WEBHOOK_CALLBACK_URL` | ✅ Yes | Public HTTPS endpoint for webhooks | `https://app.up.railway.app/webhooks/strava` |
| `STRAVA_CLIENT_ID` | ✅ Yes | Your Strava app client ID | `12345` |
| `STRAVA_CLIENT_SECRET` | ✅ Yes | Your Strava app client secret | `abc123...` |

### Webhook Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhooks/strava` | GET | Webhook verification (Strava calls this) |
| `/webhooks/strava` | POST | Receive webhook events (Strava calls this) |
| `/webhooks/strava/status` | GET | Monitor webhook health (you call this) |

## 🐛 Common Issues

### Issue: "Verification failed"

**Cause:** Wrong verify token or endpoint not accessible

**Fix:**
1. Check `STRAVA_WEBHOOK_VERIFY_TOKEN` matches in Railway
2. Verify endpoint is public and returns 200 OK
3. Check Railway logs for verification request

### Issue: "Subscription already exists"

**Cause:** You already have a webhook registered

**Fix:**
```bash
# View existing subscription
python -m src.scripts.manage_webhook_subscription view

# Delete it
python -m src.scripts.manage_webhook_subscription delete <subscription_id>

# Create new one
python -m src.scripts.manage_webhook_subscription create
```

### Issue: "Events not processing"

**Cause:** Background processing failing

**Fix:**
1. Check Railway logs for errors
2. Verify athlete has valid Strava tokens
3. Check `webhook_events` table for error messages
4. Retry failed events manually

## 📊 Monitoring

### Check Event Status

```sql
-- Event counts by status
SELECT status, COUNT(*)
FROM webhook_events
GROUP BY status;

-- Recent events
SELECT *
FROM webhook_events
ORDER BY received_at DESC
LIMIT 10;

-- Failed events
SELECT id, object_id, error_message
FROM webhook_events
WHERE status = 'failed';
```

### Railway Logs

Watch for these log patterns:

**Good:**
```
📬 Webhook received: activity.create (object_id=123456, owner_id=789)
✅ Webhook event stored: ID=1
✅ Event 1 processed successfully
```

**Bad:**
```
❌ Webhook verification failed - invalid token
❌ Failed to store webhook event: ...
❌ Event processing failed for event 1: ...
```

## 🔄 Rollback Plan

If webhooks cause issues:

### Option 1: Disable webhook subscription

```bash
# Delete subscription (stops receiving events)
python -m src.scripts.manage_webhook_subscription delete <subscription_id>

# Re-enable cron job
# Edit .github/workflows/staging-cron.yml
# Remove the conditional: if: ${{ vars.RUN_STAGING_CRON == 'true' }}
```

### Option 2: Rollback deployment

```bash
# On Railway dashboard
# Go to Deployments → Select previous deployment → Redeploy
```

## 🎉 Success Criteria

Your webhook system is working correctly when:

1. ✅ Subscription shows as "active" in Strava
2. ✅ Test activity appears in app within 30 seconds
3. ✅ `webhook_events` table has "completed" status entries
4. ✅ Activities table has the new activity
5. ✅ No errors in Railway logs
6. ✅ Status endpoint returns healthy stats

## 📚 Additional Resources

- [Setup Guide](./webhook-setup-guide.md) - Detailed setup instructions
- [Strava API Docs](https://developers.strava.com/docs/webhooks/) - Official documentation
- [Railway Docs](https://docs.railway.app/) - Deployment platform
- [Project README](../README.md) - General project documentation

## 🆘 Need Help?

**Quick Checks:**
1. Railway logs: https://railway.app/project/[your-project]/logs
2. Database: `SELECT * FROM webhook_events ORDER BY received_at DESC`
3. Status endpoint: `https://your-app.up.railway.app/webhooks/strava/status`

**Debug Commands:**
```bash
# Check subscription
python -m src.scripts.manage_webhook_subscription view

# Test endpoint
curl -v https://your-app.up.railway.app/webhooks/strava/status

# Check database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM webhook_events"
```
