# Database Backup Setup Guide

This guide will help you set up automated database backups for the Smart Marathon Coach application.

## Quick Start

### 1. Set Up Cloud Storage (AWS S3)

**Option A: AWS S3 (Recommended - ~$0.25/month)**

1. Create an S3 bucket:
   ```bash
   aws s3 mb s3://smartcoach-backups --region us-east-1
   ```

2. Create IAM user with S3 access:
   - Go to AWS IAM Console
   - Create new user: `smartcoach-backups`
   - Attach policy: `AmazonS3FullAccess` (or create custom policy for specific bucket)
   - Save Access Key ID and Secret Access Key

**Option B: Local Storage (For Testing)**

No setup needed - backups will be stored in `./backups` directory.

### 2. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:

```
DATABASE_URL              # Your Railway production database URL
AWS_ACCESS_KEY_ID         # AWS access key (if using S3)
AWS_SECRET_ACCESS_KEY    # AWS secret key (if using S3)
BACKUP_S3_BUCKET         # S3 bucket name (e.g., smartcoach-backups)
BACKUP_S3_REGION          # AWS region (e.g., us-east-1)
BACKUP_STORAGE_TYPE       # Storage type: "s3" or "local"
```

### 3. Test Backup Manually

**Test locally:**
```bash
# Set environment variables
export DATABASE_URL="postgresql://..."
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export BACKUP_S3_BUCKET="smartcoach-backups"
export BACKUP_S3_REGION="us-east-1"

# Run backup
python scripts/backup_database.py
```

**Test via GitHub Actions:**
1. Go to Actions tab in GitHub
2. Select "Database Backup" workflow
3. Click "Run workflow" → "Run workflow"

### 4. Verify Backup

**List backups in S3:**
```bash
aws s3 ls s3://smartcoach-backups/backups/
```

**Download a backup:**
```bash
aws s3 cp s3://smartcoach-backups/backups/backup_20241112_020000.sql ./
```

## Manual Backup

Run backup manually at any time:

```bash
python scripts/backup_database.py
```

With custom options:
```bash
python scripts/backup_database.py \
  --storage s3 \
  --bucket my-custom-bucket \
  --region us-west-2 \
  --retention-days 14
```

## Restore from Backup

**Restore latest backup:**
```bash
python scripts/restore_database.py --latest
```

**Restore specific backup:**
```bash
python scripts/restore_database.py --backup backup_20241112_020000.sql
```

**Restore to staging database:**
```bash
export STAGING_DATABASE_URL="postgresql://..."
python scripts/restore_database.py \
  --latest \
  --database-url $STAGING_DATABASE_URL
```

## Troubleshooting

### Backup fails: "DATABASE_URL not set"
- Make sure `DATABASE_URL` is exported in your environment
- Or pass it via `--database-url` argument (not recommended for production)

### Backup fails: "pg_dump not found"
- Install PostgreSQL client tools:
  - **Ubuntu/Debian:** `sudo apt-get install postgresql-client`
  - **macOS:** `brew install postgresql`
  - **Windows:** Download from https://www.postgresql.org/download/

### S3 upload fails: "AWS credentials not found"
- Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables
- Or configure AWS CLI: `aws configure`

### GitHub Actions fails
- Check that all secrets are set in GitHub repository settings
- Verify `DATABASE_URL` is accessible from GitHub Actions (Railway allows external connections)
- Check workflow logs for detailed error messages

## Cost Estimation

For a typical 10 GB database:
- **AWS S3 storage:** ~$0.23/month (first 5 GB free for 12 months)
- **S3 requests:** ~$0.01/month (negligible)
- **Total:** ~$0.25/month

## Next Steps

1. ✅ Set up S3 bucket and credentials
2. ✅ Configure GitHub secrets
3. ✅ Test backup manually
4. ✅ Verify automated backup runs (check GitHub Actions)
5. ✅ Test restore process (on staging database)
6. ✅ Document recovery procedures for your team

For detailed disaster recovery procedures, see: `docs/DISASTER_RECOVERY_PLAN.md`

