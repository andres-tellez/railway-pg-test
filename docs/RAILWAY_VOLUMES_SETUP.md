# Railway Volumes Backup Setup Guide

This guide will help you set up automated database backups using Railway Volumes.

## Overview

Railway Volumes provide persistent storage that can be mounted to your services. We'll create a volume for backups and run the backup script on Railway itself (not GitHub Actions).

---

## Step 1: Create Railway Volume

1. **Go to Railway Dashboard**
   - Navigate to your project
   - Click on your main service (or create a new service for backups)

2. **Create Volume**
   - Click on the service
   - Go to "Volumes" tab
   - Click "Create Volume"
   - **Name:** `backups`
   - **Size:** 20 GB (adjust based on your database size)
   - **Mount Path:** `/backups`
   - Click "Create"

3. **Note the Volume Details**
   - Volume will be mounted at `/backups` in your service
   - This path persists across deployments

---

## Step 2: Set Up Backup Service (Option A: Railway Cron)

### Create a Cron Service

1. **Create New Service**
   - In Railway dashboard, click "New" → "Empty Service"
   - Name: `backup-cron`

2. **Configure Service**
   - **Source:** Connect to your GitHub repository
   - **Root Directory:** `/` (or leave default)
   - **Build Command:** (leave empty or use `pip install -r requirements.txt`)
   - **Start Command:** `python scripts/backup_database.py --storage local --local-path /backups`

3. **Add Volume**
   - Go to "Volumes" tab
   - Click "Add Volume"
   - Select the `backups` volume you created
   - Mount path: `/backups`

4. **Set Environment Variables**
   - Go to "Variables" tab
   - Add: `DATABASE_URL` (your production database URL)
   - Add: `BACKUP_STORAGE_TYPE=local`
   - Add: `BACKUP_LOCAL_PATH=/backups`
   - Add: `BACKUP_RETENTION_DAYS=7`

5. **Set Up Cron Schedule**
   - Railway doesn't have built-in cron, so we'll use a different approach (see Option B)

---

## Step 2: Set Up Backup Service (Option B: Railway Scheduled Task - Recommended)

Since Railway doesn't have built-in cron, we'll use GitHub Actions but store backups in Railway Volumes via Railway CLI.

### Prerequisites

1. **Install Railway CLI** (if not already installed)
   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway**
   ```bash
   railway login
   ```

3. **Link Project**
   ```bash
   railway link
   ```

### Update GitHub Actions Workflow

The workflow will:
1. Create backup locally
2. Use Railway CLI to copy backup to Railway Volume
3. Clean up old backups

---

## Step 3: Alternative Approach - Run Backup on Railway Service

**Simplest Option:** Add backup script to your existing Railway service and run it manually or via Railway's scheduled tasks.

### Add Backup Endpoint to Your App

Create an admin endpoint that triggers backups:

```python
# In src/routes/admin_routes.py
@admin_bp.route("/backup-database", methods=["POST"])
@requires_auth
def backup_database():
    """Trigger database backup."""
    import subprocess
    from datetime import datetime

    backup_path = "/backups"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_path}/backup_{timestamp}.sql"

    try:
        # Run backup
        subprocess.run([
            "pg_dump",
            "--no-owner",
            "--no-acl",
            "--clean",
            "-f", backup_file,
            os.getenv("DATABASE_URL")
        ], check=True)

        return jsonify({
            "status": "success",
            "message": f"Backup created: {backup_file}",
            "backup_file": backup_file
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

Then call this endpoint via Railway's scheduled HTTP requests or external cron service.

---

## Step 4: Recommended Setup - Railway Service with Volume

**Best Approach:** Create a dedicated backup service that runs on Railway.

### 1. Create Backup Service Script

Create `scripts/railway_backup_service.py`:

```python
#!/usr/bin/env python3
"""
Railway Backup Service

Runs on Railway and creates backups to mounted volume.
Can be triggered via HTTP endpoint or run as a service.
"""
import os
import time
import subprocess
from datetime import datetime
from pathlib import Path

BACKUP_PATH = os.getenv("BACKUP_LOCAL_PATH", "/backups")
RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))

def create_backup():
    """Create database backup."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{BACKUP_PATH}/backup_{timestamp}.sql"

    Path(BACKUP_PATH).mkdir(parents=True, exist_ok=True)

    subprocess.run([
        "pg_dump",
        "--no-owner",
        "--no-acl",
        "--clean",
        "-f", backup_file,
        db_url
    ], check=True)

    print(f"✅ Backup created: {backup_file}")
    cleanup_old_backups()
    return backup_file

def cleanup_old_backups():
    """Remove backups older than retention period."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)

    backup_dir = Path(BACKUP_PATH)
    if not backup_dir.exists():
        return

    deleted = 0
    for backup_file in backup_dir.glob("backup_*.sql"):
        file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
        if file_time < cutoff:
            backup_file.unlink()
            deleted += 1
            print(f"🗑️  Deleted old backup: {backup_file.name}")

    if deleted > 0:
        print(f"✅ Cleaned up {deleted} old backup(s)")

if __name__ == "__main__":
    # Run backup
    create_backup()
```

### 2. Create Railway Service

1. **Create New Service in Railway**
   - Name: `backup-service`
   - Source: Your GitHub repository

2. **Configure Service**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python scripts/railway_backup_service.py`
   - **Or** use a web server that triggers backups on schedule

3. **Add Volume**
   - Mount the `backups` volume at `/backups`

4. **Set Environment Variables**
   - `DATABASE_URL` - Your production database URL
   - `BACKUP_LOCAL_PATH=/backups`
   - `BACKUP_RETENTION_DAYS=7`

### 3. Schedule Backups

**Option A: Use External Cron Service**
- Use a service like cron-job.org or EasyCron
- Set up daily HTTP request to trigger backup endpoint

**Option B: Use GitHub Actions with Railway CLI**
- GitHub Actions runs backup script
- Uses Railway CLI to copy backup to volume
- See updated workflow below

---

## Step 5: GitHub Actions + Railway CLI (Hybrid Approach)

This approach uses GitHub Actions to run backups but stores them in Railway Volumes.

### Update GitHub Actions Workflow

```yaml
name: Database Backup to Railway Volume

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
  workflow_dispatch:

jobs:
  backup:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install PostgreSQL client
        run: |
          sudo apt-get update
          sudo apt-get install -y postgresql-client

      - name: Install Railway CLI
        run: npm install -g @railway/cli

      - name: Login to Railway
        run: railway login --browserless
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}

      - name: Create backup
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          python scripts/backup_database.py \
            --storage local \
            --local-path ./backups \
            --output-dir ./backups

      - name: Copy backup to Railway Volume
        run: |
          railway link ${{ secrets.RAILWAY_PROJECT_ID }}
          railway run --service backup-service -- \
            cp ./backups/backup_*.sql /backups/
```

**Note:** This approach is more complex. The simpler option is to run backups directly on Railway.

---

## Recommended: Simple Railway Service Approach

**Easiest Setup:**

1. **Create Volume** (as described in Step 1)

2. **Add Backup Endpoint to Your Main Service**
   - Add the `/admin/backup-database` endpoint (see code above)
   - Mount the `backups` volume to your main service at `/backups`

3. **Schedule via External Service**
   - Use cron-job.org (free)
   - Set up daily HTTP POST to: `https://your-app.railway.app/admin/backup-database`
   - Include authentication header

4. **Or Run Manually**
   - Call the endpoint when needed
   - Backups stored in Railway Volume

---

## Testing

### Test Backup Locally

```bash
# Set environment variables
export DATABASE_URL="your-database-url"
export BACKUP_LOCAL_PATH="./backups"

# Run backup
python scripts/backup_database.py --storage local --local-path ./backups

# Verify backup created
ls -lh ./backups/
```

### Test on Railway

1. **SSH into Railway Service** (if available)
   ```bash
   railway shell
   ```

2. **Check Volume Mount**
   ```bash
   ls -la /backups
   ```

3. **Run Backup Manually**
   ```bash
   python scripts/backup_database.py --storage local --local-path /backups
   ```

---

## Restore from Railway Volume

```bash
# List backups
railway run --service your-service -- ls -lh /backups/

# Download backup
railway run --service your-service -- cat /backups/backup_20241112_020000.sql > restore.sql

# Restore to database
psql $DATABASE_URL -f restore.sql
```

---

## Cost Estimation

**Railway Volumes:**
- Storage: $0.15/GB/month
- Example: 20 GB volume = $3.00/month
- No egress charges (backups stay on Railway)

**Comparison:**
- Railway Volumes: $3.00/month (20 GB)
- AWS S3: $0.46/month (20 GB)
- Backblaze B2: $0.10/month (20 GB)

Railway Volumes are more expensive but simpler to set up and manage.

---

## Next Steps

1. ✅ Create Railway Volume
2. ✅ Choose backup approach (service endpoint or dedicated service)
3. ✅ Set up scheduled triggers
4. ✅ Test backup and restore
5. ✅ Monitor backup storage usage

For detailed disaster recovery procedures, see: `docs/DISASTER_RECOVERY_PLAN.md`
