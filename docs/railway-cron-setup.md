# Railway Cron Job Setup (Alternative to Worker Service)

This guide shows how to use **Railway's native Cron Jobs** instead of running a separate worker service.

## 🎯 Two Options

You have **two ways** to run the weekly scheduler:

### **Option 1: Railway Cron Jobs** (Recommended - Simpler) ✅
- ✅ No separate service needed
- ✅ Railway manages the schedule
- ✅ Less resources (only runs when needed)
- ❌ Slightly less visibility (logs in cron execution, not continuous)

### **Option 2: Separate Worker Service** (Current Setup)
- ✅ Continuous visibility (always-running service)
- ✅ Can manually trigger via service restart
- ❌ Uses resources 24/7
- ❌ Requires manual service setup in Railway

---

## 🚀 Setup: Railway Cron Jobs (Option 1)

### Step 1: Add Cron Job in Railway

1. Go to Railway Dashboard: https://railway.app
2. Select your project
3. Go to **Settings** (gear icon)
4. Scroll to **Cron Jobs** section
5. Click **+ Add Cron Job**

### Step 2: Configure the Cron Job

**Schedule:**
```
30 5 * * 0
```
(This runs every **Sunday at 05:30 UTC**, which is **Saturday 11:30 PM Central Time (CST)**)

**Command:**
```
RUN_ONCE=true python src/scripts/metrics_scheduler.py
```

**Note:** The `RUN_ONCE=true` environment variable tells the scheduler to run once and exit (instead of running as a long-running worker).

### Step 3: Save

Click **Save** and Railway will start running the job automatically.

---

## ⚠️ Important: DST (Daylight Saving Time)

**Central Time** has two offsets:
- **CST (winter)**: UTC-6
- **CDT (summer)**: UTC-5

**Current Schedule (using CST):**
- **CST (winter)**: Saturday 11:30 PM CT = Sunday 05:30 UTC ✅
- **CDT (summer)**: Saturday 11:30 PM CT = Sunday 04:30 UTC (runs 1 hour earlier)

**If you want it to run at exactly 11:30 PM CT year-round**, you'll need to:
1. Use CDT schedule: `30 4 * * 0` (runs at 11:30 PM CDT, but 12:30 AM during CST)
2. OR manually adjust the cron schedule twice a year when DST changes

**Recommendation:** Use the CST schedule (`30 5 * * 0`) and accept that during summer it runs 1 hour earlier, OR adjust manually for DST.

---

## 🧪 Test It

### Test the Script Locally

```bash
# Test run-once mode locally
RUN_ONCE=true python src/scripts/metrics_scheduler.py
```

Expected output:
```
[SCHEDULER] Running in cron mode (run once)...
🚀 Running weekly scheduled tasks (cron mode)...
```

### Test in Railway

After adding the cron job, Railway will run it automatically. Check the logs:
1. Go to Railway Dashboard → **Logs** (top navigation)
2. Filter for cron job executions
3. Look for `[SCHEDULER]` messages

---

## 📋 Cron Schedule Reference

**Current Schedule:** `30 5 * * 0`
- Format: `minute hour day month weekday`
- `30 5 * * 0` = Every Sunday at 05:30 UTC

**Other Options:**

| Time (Central) | Cron Schedule (UTC) | Notes |
|---------------|---------------------|-------|
| Saturday 11:30 PM CST | `30 5 * * 0` | Current (winter) |
| Saturday 11:30 PM CDT | `30 4 * * 0` | Summer time |
| Saturday 10:30 PM CST | `30 4 * * 0` | Earlier option |
| Sunday 12:00 AM CST | `0 6 * * 0` | Just after midnight CT |

---

## 🔧 Switching Between Options

### To Switch to Cron Jobs (Option 1):
1. Follow setup above
2. **No need to remove** the worker service (you can keep both if you want)

### To Switch to Worker Service (Option 2):
1. Create a new service in Railway named `cron_scheduler`
2. Set start command: `python src/scripts/metrics_scheduler.py` (without `RUN_ONCE=true`)
3. Remove the cron job from Settings

---

## ✅ Done!

Your weekly scheduler will now run automatically via Railway cron jobs. You'll see execution logs in Railway's **Logs** view.
