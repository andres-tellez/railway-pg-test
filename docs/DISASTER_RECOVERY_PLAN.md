# Disaster Recovery Plan

**Last Updated:** November 2024  
**Owner:** DevOps Team  
**Review Frequency:** Quarterly

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Current Backup Strategy](#current-backup-strategy)
3. [Recovery Objectives](#recovery-objectives)
4. [Disaster Scenarios](#disaster-scenarios)
5. [Recovery Procedures](#recovery-procedures)
6. [Backup Management](#backup-management)
7. [Testing & Validation](#testing--validation)
8. [Enhancement Log](#enhancement-log)

---

## Overview

This document outlines the disaster recovery (DR) strategy for the Smart Marathon Coach application hosted on Railway. The primary goal is to ensure data integrity and minimize downtime in the event of database failures, data corruption, or accidental data loss.

### Key Components

- **Database:** PostgreSQL on Railway
- **Backup Storage:** AWS S3 (or alternative cloud storage)
- **Backup Frequency:** Daily automated backups
- **Retention Policy:** 7 days daily, 4 weeks weekly, 12 months monthly
- **Recovery Method:** Point-in-time restore from SQL dumps

---

## Current Backup Strategy

### Automated Backups

**Schedule:** Daily at 2:00 AM UTC (via GitHub Actions or external cron service)  
**Method:** PostgreSQL `pg_dump` via GitHub Actions or admin endpoint  
**Storage Location:** Backblaze B2 cloud storage  
**Scripts:** 
- `scripts/backup_database.py` (supports B2, S3, and local storage)
- Admin endpoint: `POST /admin/backup-database` (for manual backups)

### Backup Process Flow

```
1. GitHub Actions triggers at 2:00 AM UTC
2. Connects to production database via DATABASE_URL
3. Creates SQL dump using pg_dump
4. Uploads to cloud storage with timestamp
5. Applies retention policy (deletes old backups)
6. Sends notification (optional)
```

### Backup File Naming Convention

```
backup_YYYYMMDD_HHMMSS.sql
Example: backup_20241112_020000.sql
```

### What Gets Backed Up

✅ **Included:**
- All database tables and schemas
- Table structures (CREATE TABLE statements)
- All data rows
- Indexes and constraints
- Foreign key relationships

❌ **Not Included:**
- Environment variables (backed up separately)
- Application code (in Git repository)
- External API data (Strava activities can be re-synced)

---

## Recovery Objectives

### Recovery Time Objective (RTO)

**Target:** 30 minutes  
**Current:** 1-2 hours (manual process)

RTO is the maximum acceptable downtime. Our goal is to restore service within 30 minutes of disaster detection.

### Recovery Point Objective (RPO)

**Target:** 24 hours  
**Current:** 24 hours (daily backups)

RPO is the maximum acceptable data loss. With daily backups, we can lose up to 24 hours of data. However, webhook re-sync can recover most activity data automatically.

---

## Disaster Scenarios

### Scenario 1: Database Corruption

**Symptoms:**
- Application errors: "Database connection failed"
- Query errors: "relation does not exist" or "corrupted index"
- Railway dashboard shows database as unhealthy

**Recovery Steps:**
1. Verify database is unrecoverable
2. Identify last known good backup
3. Create new Railway PostgreSQL service (if needed)
4. Restore from backup using `scripts/restore_database.py`
5. Verify data integrity
6. Restart application

**Estimated Recovery Time:** 30-60 minutes

### Scenario 2: Accidental Data Deletion

**Symptoms:**
- Users report missing data
- Database queries return fewer rows than expected
- Application logs show DELETE operations

**Recovery Steps:**
1. Identify when deletion occurred
2. Select backup from before deletion
3. Restore specific tables (if possible) or full database
4. Verify restored data
5. Re-sync any missing data via webhooks (if applicable)

**Estimated Recovery Time:** 15-45 minutes

### Scenario 3: Railway Database Service Failure

**Symptoms:**
- Railway dashboard shows database service as "Failed"
- Cannot connect to database
- Railway support confirms permanent failure

**Recovery Steps:**
1. Create new PostgreSQL service in Railway
2. Get new DATABASE_URL
3. Download latest backup from cloud storage
4. Restore backup to new database
5. Update Railway environment variables (DATABASE_URL)
6. Restart application services
7. Verify application functionality

**Estimated Recovery Time:** 45-90 minutes

### Scenario 4: Data Corruption (Application Bug)

**Symptoms:**
- Data inconsistencies reported by users
- Application logs show errors during data operations
- Database queries return unexpected results

**Recovery Steps:**
1. Identify when corruption started
2. Select backup from before corruption
3. Restore database from backup
4. Investigate root cause (code bug, migration issue)
5. Fix bug in codebase
6. Deploy fix to prevent recurrence

**Estimated Recovery Time:** 1-2 hours

### Scenario 5: Security Breach / Malicious Deletion

**Symptoms:**
- Unauthorized access detected
- Data deleted or modified unexpectedly
- Security alerts triggered

**Recovery Steps:**
1. **IMMEDIATE:** Revoke compromised credentials
2. Assess extent of damage
3. Select backup from before breach
4. Restore database from backup
5. Rotate all API keys and secrets
6. Update environment variables in Railway
7. Conduct security audit
8. Implement additional security measures

**Estimated Recovery Time:** 2-4 hours

---

## Recovery Procedures

### Quick Reference: Manual Recovery

```bash
# 1. Download latest backup
aws s3 cp s3://your-backup-bucket/backups/backup_YYYYMMDD_HHMMSS.sql ./

# 2. Restore to database
psql $DATABASE_URL -f backup_YYYYMMDD_HHMMSS.sql

# 3. Verify restoration
psql $DATABASE_URL -c "SELECT COUNT(*) FROM activities;"
```

### Detailed Recovery Procedure

#### Step 1: Assess the Situation

1. **Check Railway Dashboard**
   - Go to Railway dashboard
   - Check database service status
   - Review recent logs

2. **Verify Database Connectivity**
   ```bash
   psql $DATABASE_URL -c "SELECT 1;"
   ```

3. **Identify Data Loss**
   ```bash
   # Check row counts
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM activities;"
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM user_identity;"
   ```

#### Step 2: Select Recovery Point

1. **List Available Backups**
   ```bash
   aws s3 ls s3://your-backup-bucket/backups/
   ```

2. **Choose Backup**
   - Select backup from before disaster occurred
   - Consider data loss tolerance (RPO)
   - Prefer most recent backup if possible

#### Step 3: Create New Database (If Needed)

**Only if Railway database is completely gone:**

1. Go to Railway dashboard
2. Create new PostgreSQL service
3. Copy new `DATABASE_URL`
4. Update environment variables in Railway

#### Step 4: Download Backup

```bash
# Set backup filename
BACKUP_FILE="backup_20241112_020000.sql"

# Download from S3
aws s3 cp s3://your-backup-bucket/backups/$BACKUP_FILE ./

# Verify file downloaded
ls -lh $BACKUP_FILE
```

#### Step 5: Restore Database

**Option A: Full Restore (Recommended)**

```bash
# Restore entire database
psql $DATABASE_URL -f $BACKUP_FILE

# If errors occur, try with verbose output
psql $DATABASE_URL -f $BACKUP_FILE -v ON_ERROR_STOP=1
```

**Option B: Selective Restore (Advanced)**

If you only need to restore specific tables:

```bash
# Extract specific table from backup
pg_restore -t activities $BACKUP_FILE > activities_only.sql

# Restore specific table
psql $DATABASE_URL -f activities_only.sql
```

#### Step 6: Verify Restoration

```bash
# Check critical tables
psql $DATABASE_URL <<EOF
SELECT COUNT(*) as user_count FROM user_identity;
SELECT COUNT(*) as activity_count FROM activities;
SELECT COUNT(*) as plan_count FROM plans;
SELECT MAX(created_at) as latest_activity FROM activities;
EOF
```

**Expected Results:**
- Row counts match expected values
- Latest activity timestamp is reasonable
- No error messages

#### Step 7: Update Application

1. **If New Database Created:**
   - Update `DATABASE_URL` in Railway environment variables
   - Restart Railway services

2. **Verify Application:**
   - Test critical endpoints
   - Check user authentication
   - Verify data display

3. **Monitor:**
   - Watch application logs
   - Check error rates
   - Verify user reports

#### Step 8: Post-Recovery

1. **Document Incident:**
   - Record what happened
   - Note recovery time
   - Document lessons learned

2. **Re-sync Missing Data:**
   - If webhooks are active, missing activities will auto-sync
   - Use `/admin/sync-activities` endpoint if needed

3. **Update DR Plan:**
   - Add any improvements to this document
   - Update procedures if needed

---

## Backup Management

### Backup Storage Configuration

**Current Setup:**
- **Provider:** Backblaze B2 Cloud Storage
- **Bucket Name:** `smartcoach-backups`
- **Path:** `backups/backup_YYYYMMDD_HHMMSS.sql`
- **Cost:** $0.005/GB/month (~$0.05/month for 10 GB, first 10 GB free!)

### Retention Policy

| Backup Type | Retention Period | Count |
|------------|-----------------|-------|
| Daily | Last 7 days | 7 backups |
| Weekly | Last 4 weeks | 4 backups |
| Monthly | Last 12 months | 12 backups |
| **Total** | | **~23 backups** |

**Cleanup Process:**
- Automated via backup script
- Runs after each backup creation
- Deletes backups older than retention policy

### Backup Verification

**Monthly Verification:**
1. Download a random backup
2. Verify it can be restored to test database
3. Check data integrity
4. Document results

**Script:** `scripts/verify_backup.py` (to be created)

---

## Testing & Validation

### Quarterly DR Test

**Schedule:** Every 3 months  
**Procedure:**

1. **Test Restore:**
   - Select a backup from 1 week ago
   - Restore to staging/test database
   - Verify data integrity
   - Test application functionality

2. **Document Results:**
   - Record test date
   - Note any issues
   - Update procedures if needed

3. **Review DR Plan:**
   - Update this document
   - Review RTO/RPO targets
   - Identify improvements

### Backup Integrity Checks

**Automated Checks:**
- Backup file size validation
- Backup file existence verification
- Storage quota monitoring

**Manual Checks:**
- Monthly restore test
- Quarterly full DR drill

---

## Enhancement Log

This section tracks improvements and enhancements to the DR plan.

### 2024-11-12: Initial DR Plan Created

**Added:**
- Comprehensive DR documentation
- Automated backup script (`scripts/backup_database.py`)
- Railway-specific backup service (`scripts/railway_backup_service.py`)
- Admin endpoint for manual backups (`POST /admin/backup-database`)
- Restore script (`scripts/restore_database.py`)
- GitHub Actions workflow for automated backups
- Railway Volumes setup guide

**Configuration:**
- ✅ Using Railway Volumes for backup storage
- ✅ Backup endpoint available at `/admin/backup-database`
- ✅ Automated cleanup of old backups (7-day retention)

**Next Steps:**
- [ ] Create Railway Volume (`backups`, 20 GB, mount at `/backups`)
- [ ] Set environment variables (`BACKUP_LOCAL_PATH=/backups`)
- [ ] Test backup via admin endpoint
- [ ] Set up scheduled backups (cron-job.org or GitHub Actions)
- [ ] Test restore process
- [ ] Set up backup verification
- [ ] Implement automated restore (future enhancement)

### Future Enhancements

**Planned:**
- [ ] Automated restore script
- [ ] Point-in-time recovery (PITR) if Railway supports it
- [ ] Cross-region backup replication
- [ ] Backup encryption at rest
- [ ] Automated DR testing
- [ ] Monitoring and alerting for backup failures
- [ ] Database replication (read replicas)

**Under Consideration:**
- [ ] Hourly backups for critical data
- [ ] Database-level replication
- [ ] Multi-region deployment
- [ ] Automated failover

---

## Emergency Contacts

**Railway Support:**
- Dashboard: https://railway.app
- Support: support@railway.app

**AWS Support (if using S3):**
- Console: https://console.aws.amazon.com
- Support: AWS Support Center

**Team Contacts:**
- [Add team contact information]

---

## Appendix

### Backup Script Usage

```bash
# Manual backup (for testing)
python scripts/backup_database.py

# With custom storage
python scripts/backup_database.py --storage s3 --bucket my-bucket
```

### Restore Script Usage

```bash
# Restore from latest backup
python scripts/restore_database.py

# Restore from specific backup
python scripts/restore_database.py --backup backup_20241112_020000.sql

# Restore to different database
python scripts/restore_database.py --database-url $STAGING_DATABASE_URL
```

### Environment Variables

Required for backup/restore:

```bash
DATABASE_URL=postgresql://...          # Production database
BACKUP_STORAGE_TYPE=s3                 # s3, local, or volume
AWS_ACCESS_KEY_ID=...                  # If using S3
AWS_SECRET_ACCESS_KEY=...              # If using S3
BACKUP_S3_BUCKET=smartcoach-backups   # S3 bucket name
BACKUP_S3_REGION=us-east-1            # S3 region
```

---

**Document Version:** 1.0  
**Last Reviewed:** November 2024  
**Next Review:** February 2025

