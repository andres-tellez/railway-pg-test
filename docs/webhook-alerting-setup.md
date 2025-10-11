# Webhook Health Alerting Setup

Automatic Discord notifications when webhook processing fails.

## 🎯 What You Get

- **Daily health checks** via Railway cron
- **Instant Discord alerts** when failures detected
- **Mobile notifications** on your phone
- **Zero cost** - completely free

---

## 📋 Setup Instructions (5 minutes)

### Step 1: Create Discord Webhook (2 min)

1. Open Discord
2. Go to your server → **Server Settings** → **Integrations**
3. Click **Webhooks** → **New Webhook**
4. Name it: `Webhook Monitor`
5. Choose a channel (e.g., `#alerts` or `#monitoring`)
6. **Copy Webhook URL** (looks like: `https://discord.com/api/webhooks/123456...`)

### Step 2: Add to Railway (1 min)

1. Go to Railway Dashboard: https://railway.app
2. Select your project
3. Click **Variables** (in left sidebar)
4. Click **+ New Variable**
5. Add:
   ```
   Variable: ALERT_WEBHOOK_URL
   Value: [paste your Discord webhook URL]
   ```
6. Save

### Step 3: Set Up Daily Cron Job (2 min)

1. In Railway Dashboard, go to **Settings**
2. Scroll to **Cron Jobs** section
3. Click **+ Add Cron Job**
4. Configure:
   ```
   Schedule: 0 9 * * *
   Command: python -m src.scripts.webhook_health_alert
   ```
   (This runs daily at 9 AM UTC)
5. Save

---

## ✅ Done!

You'll now receive a Discord notification every morning **ONLY IF** there are webhook issues:

- ❌ Failed events (> 10 failures)
- ⏳ Stuck events (pending > 5 minutes)
- 🚫 No events at all (webhook broken)

**No news is good news!** If everything is healthy, you won't get any messages.

---

## 🧪 Test It

Want to test the alert? Run manually:

```bash
# SSH into Railway or run locally
python -m src.scripts.webhook_health_alert
```

If webhooks are healthy, you'll see:
```
[SUCCESS] Webhook system is healthy!
[INFO] No alerts needed - system is healthy
```

If there are issues, you'll get a Discord notification!

---

## 🔧 Customize

### Change Alert Time

Edit the cron schedule:
- `0 9 * * *` = 9 AM UTC daily
- `0 14 * * *` = 2 PM UTC daily
- `0 */6 * * *` = Every 6 hours
- `0 9 * * 1-5` = 9 AM weekdays only

### Add Multiple Webhooks

Set multiple webhook URLs (comma-separated):
```
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/url1,https://discord.com/api/webhooks/url2
```

### Add Slack Instead

Works with Slack incoming webhooks too:
```
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
```

---

## 📊 What Gets Monitored

The health check monitors:

1. **Overall Stats** - Total events by status
2. **Recent Failures** - Failed events in last 24 hours
3. **Stuck Events** - Events pending > 5 minutes
4. **Recent Activity** - Events in last hour
5. **Success Rate** - 7-day success percentage

**Alert Threshold:** You get notified if:
- More than 10 failed events, OR
- Any events stuck in pending > 5 minutes, OR
- No webhook events received at all

---

## 🆘 Troubleshooting

### Not Receiving Alerts?

1. **Check Railway logs:**
   ```
   Railway Dashboard → Deployments → Logs
   Filter for: "webhook_health_alert"
   ```

2. **Verify webhook URL is set:**
   ```
   Railway Dashboard → Variables
   Look for: ALERT_WEBHOOK_URL
   ```

3. **Test Discord webhook manually:**
   ```bash
   curl -X POST https://discord.com/api/webhooks/YOUR_URL \
     -H "Content-Type: application/json" \
     -d '{"content": "Test message"}'
   ```

### Getting Too Many Alerts?

Increase alert thresholds in `src/scripts/webhook_health_alert.py`:
```python
# Change line 191 from:
elif failed_count > 10:

# To:
elif failed_count > 50:  # More tolerant
```

---

## 🎉 You're Done!

Your webhook system now has:
- ✅ Real-time event processing (webhooks)
- ✅ Manual historical fetch (`/admin/fetch-activity/<id>`)
- ✅ Health monitoring (`/webhooks/strava/status`)
- ✅ Automatic daily checks (cron)
- ✅ Discord alerts (when things break)

Sleep well knowing you'll be notified if anything goes wrong! 😴
