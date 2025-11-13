# Railway Backup Quick Start Guide

Get automated database backups running in 5 minutes using Railway Volumes.

---

## Step 1: Create Railway Volume (2 minutes)

1. **Go to Railway Dashboard**
   - Navigate to your project
   - Click on your main service (the one running your Flask app)

2. **Create Volume**
   - Click "Volumes" tab
   - Click "Create Volume"
   - **Name:** `backups`
   - **Size:** 20 GB (or adjust based on your needs)
   - **Mount Path:** `/backups`
   - Click "Create"

✅ **Done!** Your volume is now mounted at `/backups`

---

## Step 2: Add Environment Variables (1 minute)

In your Railway service, go to "Variables" tab and add:

```
BACKUP_LOCAL_PATH=/backups
BACKUP_RETENTION_DAYS=7
```

(Your `DATABASE_URL` should already be set)

---

## Step 3: Test Backup (1 minute)

### Option A: Use Admin Endpoint (Easiest)

Call the backup endpoint:

```bash
# Get your auth token first, then:
curl -X POST https://your-app.railway.app/admin/backup-database \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Option B: Run Script Manually

If you have Railway CLI:

```bash
railway run python scripts/railway_backup_service.py
```

---

## Step 4: Schedule Automated Backups (1 minute)

### Option A: External Cron Service (Recommended)

Use a free service like **cron-job.org**:

1. **Sign up:** https://cron-job.org (free)
2. **Create new cron job:**
   - **URL:** `https://your-app.railway.app/admin/backup-database`
   - **Method:** POST
   - **Schedule:** Daily at 2:00 AM UTC
   - **Headers:** `Authorization: Bearer YOUR_TOKEN`
   - **Save**

### Option B: GitHub Actions (Alternative)

If you prefer GitHub Actions, update `.github/workflows/database-backup.yml` to use Railway CLI (see full guide).

---

## Verify It Works

1. **Check backups exist:**
   ```bash
   # Via Railway CLI
   railway run --service your-service -- ls -lh /backups/
   ```

2. **Or check via admin endpoint:**
   ```bash
   curl https://your-app.railway.app/admin/backup-database \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
   Response will show recent backups.

---

## Restore from Backup

```bash
# List backups
railway run --service your-service -- ls -lh /backups/

# Download backup
railway run --service your-service -- cat /backups/backup_20241112_020000.sql > restore.sql

# Restore to database
psql $DATABASE_URL -f restore.sql
```

Or use the restore script:

```bash
python scripts/restore_database.py \
  --backup backup_20241112_020000.sql \
  --storage local \
  --local-path /backups
```

---

## Cost

**Railway Volumes:** $0.15/GB/month
- 20 GB volume = **$3.00/month**
- No egress charges
- No API costs

---

## Troubleshooting

### "pg_dump not found"
Railway's base images include PostgreSQL client. If missing, add to your Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y postgresql-client
```

### "Permission denied" on /backups
Make sure the volume is mounted correctly in Railway dashboard.

### Backups not appearing
- Check volume is mounted: `railway run -- ls -la /backups`
- Check environment variables are set
- Check Railway logs for errors

---

## Next Steps

- ✅ Set up automated daily backups
- ✅ Test restore process
- ✅ Monitor backup storage usage
- ✅ Review `docs/DISASTER_RECOVERY_PLAN.md` for full DR procedures

---

**That's it!** You now have automated database backups running on Railway. 🎉

