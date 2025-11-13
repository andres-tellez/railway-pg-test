# Create Railway Volume via CLI

Since volumes aren't visible in the UI for `backend-prod`, we'll create it using Railway CLI.

## Step 1: Install Railway CLI (if not already installed)

```bash
npm install -g @railway/cli
```

## Step 2: Login to Railway

```bash
railway login
```

This will open your browser to authenticate.

## Step 3: Link to Your Project

```bash
railway link
```

Select your project (`supportive-reprieve`) and environment (`production`).

## Step 4: Create Volume

```bash
railway volume create backups --size 20
```

This creates a 20 GB volume named `backups`.

## Step 5: Mount Volume to Service

```bash
railway volume mount backups --service backend-prod --mount-path /backups
```

## Step 6: Verify Volume is Mounted

```bash
railway volume list
```

You should see the `backups` volume listed.

---

## Alternative: Use Railway Dashboard

If CLI doesn't work, try:

1. Go back to project view (click project name)
2. Look for "Volumes" section (might be at project level)
3. Or check if volumes can be added via the service's "Deploy" or "Build" settings

---

## Alternative Approach: Use Existing Volume

Since `db-prod` already has `heartfelt-volume`, you could:

1. Mount that volume to `backend-prod` as well (if Railway allows multiple mounts)
2. Or store backups in a different location (S3, etc.)

---

## Quick Test After Setup

Once volume is created and mounted:

```bash
# Set environment variable in Railway dashboard
BACKUP_LOCAL_PATH=/backups

# Test backup via admin endpoint
curl -X POST https://prod.smartcoach.dev/admin/backup-database \
  -H "Authorization: Bearer YOUR_TOKEN"
```

