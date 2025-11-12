# Backblaze B2 Setup Guide

Complete guide to set up Backblaze B2 for database backups.

---

## Step 1: Create Backblaze Account (2 minutes)

1. **Go to Backblaze B2**
   - Visit: https://www.backblaze.com/b2/sign-up.html
   - Click "Sign Up" (free account)

2. **Complete Signup**
   - Enter your email
   - Create password
   - Verify email

**✅ Free Tier Includes:**
- 10 GB storage free forever
- No credit card required initially

---

## Step 2: Create B2 Bucket (1 minute)

1. **Login to Backblaze**
   - Go to: https://secure.backblaze.com/user_signin.htm
   - Login with your credentials

2. **Navigate to B2 Cloud Storage**
   - Click "B2 Cloud Storage" in the left menu
   - Or go directly to: https://secure.backblaze.com/b2_buckets.htm

3. **Create Bucket**
   - Click "Create a Bucket" button
   - **Bucket Name:** `smartcoach-backups` (must be globally unique)
   - **Files in Bucket are:** Private
   - **Default Encryption:** Enabled (recommended)
   - Click "Create a Bucket"

**✅ Bucket Created!** Note the bucket name.

---

## Step 3: Create Application Key (2 minutes)

1. **Go to App Keys**
   - In B2 Cloud Storage, click "App Keys" in left menu
   - Or go to: https://secure.backblaze.com/b2_buckets.htm

2. **Add New Application Key**
   - Click "Add a New Application Key"
   - **Name:** `smartcoach-backups` (or any name)
   - **Allow List All Bucket Names:** ✅ Checked
   - **Allow List Files:** ✅ Checked
   - **Allow Read Files:** ✅ Checked
   - **Allow Share Files:** ✅ Checked
   - **Allow Write Files:** ✅ Checked
   - **Allow Delete Files:** ✅ Checked
   - **File Name Prefix:** Leave empty (or use `backups/` to restrict to backups folder)
   - **Duration:** Leave empty (no expiration)
   - Click "Create New Key"

3. **Save Your Credentials**
   - **Key ID:** Copy this (e.g., `003a1b2c3d4e5f6g7h8i9j0k1l2m3n`)
   - **Application Key:** Copy this (e.g., `K001a1b2c3d4e5f6g7h8i9j0k1l2m3n`)
   - **⚠️ IMPORTANT:** Save these securely - you won't see the Application Key again!

---

## Step 4: Add to Railway Environment Variables

1. **Go to Railway Dashboard**
   - Navigate to your `backend-prod` service
   - Click "Variables" tab

2. **Add Environment Variables**
   Click "New Variable" for each:

   ```
   B2_APPLICATION_KEY_ID=003a1b2c3d4e5f6g7h8i9j0k1l2m3n
   B2_APPLICATION_KEY=K001a1b2c3d4e5f6g7h8i9j0k1l2m3n
   B2_BUCKET_NAME=smartcoach-backups
   BACKUP_STORAGE_TYPE=b2
   ```

   Replace with your actual values from Step 3.

---

## Step 5: Add to GitHub Secrets (for GitHub Actions)

If using GitHub Actions for automated backups:

1. **Go to GitHub Repository**
   - Navigate to: Settings → Secrets and variables → Actions

2. **Add Secrets**
   Click "New repository secret" for each:

   ```
   B2_APPLICATION_KEY_ID
   B2_APPLICATION_KEY
   B2_BUCKET_NAME
   BACKUP_STORAGE_TYPE=b2
   DATABASE_URL (your Railway database URL)
   ```

---

## Step 6: Install B2 SDK (if running locally)

```bash
pip install b2sdk
```

Or add to `requirements.txt` (already added):
```
b2sdk==1.25.0
```

---

## Step 7: Test Backup

### Test Locally

```bash
# Set environment variables
export B2_APPLICATION_KEY_ID="your-key-id"
export B2_APPLICATION_KEY="your-application-key"
export B2_BUCKET_NAME="smartcoach-backups"
export BACKUP_STORAGE_TYPE="b2"
export DATABASE_URL="your-database-url"

# Run backup
python scripts/backup_database.py --storage b2
```

### Test via Admin Endpoint

```bash
# Call admin endpoint (if you added B2 support to it)
curl -X POST https://prod.smartcoach.dev/admin/backup-database \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Verify Backup in B2

1. Go to Backblaze B2 dashboard
2. Click on your bucket (`smartcoach-backups`)
3. Navigate to `backups/` folder
4. You should see: `backup_YYYYMMDD_HHMMSS.sql`

---

## Step 8: Update GitHub Actions Workflow

Update `.github/workflows/database-backup.yml`:

```yaml
- name: Install Python dependencies
  run: |
    python -m pip install --upgrade pip
    pip install b2sdk  # Add this

- name: Create database backup
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
    B2_APPLICATION_KEY_ID: ${{ secrets.B2_APPLICATION_KEY_ID }}
    B2_APPLICATION_KEY: ${{ secrets.B2_APPLICATION_KEY }}
    B2_BUCKET_NAME: ${{ secrets.B2_BUCKET_NAME }}
    BACKUP_STORAGE_TYPE: b2
  run: |
    python scripts/backup_database.py --storage b2
```

---

## Cost Estimation

**Backblaze B2 Pricing:**
- **Storage:** $0.005/GB/month (first 10 GB free!)
- **Download:** $0.01/GB (first 1 GB free per day)
- **Upload:** Free

**Example (10 GB database, daily backups):**
- Storage: 10 GB × $0.005 = **$0.05/month**
- Downloads: Rarely needed, ~$0.01/month
- **Total: ~$0.06/month** (vs $3/month for Railway Volumes!)

**First 10 GB is FREE forever!**

---

## Troubleshooting

### "b2sdk not installed"
```bash
pip install b2sdk
```

### "B2 credentials not found"
- Check environment variables are set correctly
- Verify `B2_APPLICATION_KEY_ID` and `B2_APPLICATION_KEY` are correct
- Make sure no extra spaces or quotes

### "Bucket not found"
- Verify bucket name matches exactly (case-sensitive)
- Check bucket exists in Backblaze dashboard
- Ensure Application Key has access to bucket

### "Permission denied"
- Check Application Key has "Write Files" permission
- Verify bucket name is correct
- Check Application Key hasn't been deleted

### Upload fails silently
- Check B2 dashboard for error messages
- Verify Application Key hasn't expired
- Check bucket is not in "All Public" mode (should be Private)

---

## Security Best Practices

1. ✅ **Use Private Buckets** - Don't make buckets public
2. ✅ **Restrict Application Key** - Use file name prefix (`backups/`) if possible
3. ✅ **Rotate Keys** - Create new keys periodically
4. ✅ **Never Commit Keys** - Use environment variables/secrets only
5. ✅ **Enable Encryption** - Use default encryption on bucket

---

## Restore from B2

```bash
# List backups
python scripts/restore_database.py --storage b2 --latest --no-verify

# Restore specific backup
python scripts/restore_database.py \
  --storage b2 \
  --backup backup_20241112_020000.sql
```

---

## Next Steps

1. ✅ Set up B2 account and bucket
2. ✅ Add credentials to Railway
3. ✅ Test backup manually
4. ✅ Set up automated backups (GitHub Actions or cron)
5. ✅ Test restore process
6. ✅ Monitor backup storage usage

---

**That's it!** You now have cheap, reliable cloud backups using Backblaze B2. 🎉

**Cost:** ~$0.06/month (vs $3/month for Railway Volumes)  
**Storage:** 10 GB free forever  
**Reliability:** Enterprise-grade cloud storage

