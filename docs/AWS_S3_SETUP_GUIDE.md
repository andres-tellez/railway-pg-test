# AWS S3 Setup Guide for Database Backups

This guide will walk you through setting up AWS S3 to store your database backups.

## Prerequisites

- An AWS account (free tier is fine)
- AWS CLI installed (optional but recommended)

---

## Step 1: Create AWS Account (If You Don't Have One)

1. Go to https://aws.amazon.com/
2. Click "Create an AWS Account"
3. Follow the signup process
4. **Note:** AWS offers 12 months free tier, which includes:
   - 5 GB of S3 storage
   - 20,000 GET requests
   - 2,000 PUT requests

---

## Step 2: Install AWS CLI (Optional but Recommended)

**Windows (PowerShell):**
```powershell
# Download AWS CLI installer
# Visit: https://awscli.amazonaws.com/AWSCLIV2.msi
# Or use winget:
winget install Amazon.AWSCLI
```

**macOS:**
```bash
brew install awscli
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Verify installation:**
```bash
aws --version
```

---

## Step 3: Create S3 Bucket

### Option A: Using AWS Console (Easiest)

1. **Log in to AWS Console**
   - Go to https://console.aws.amazon.com/
   - Sign in with your AWS account

2. **Navigate to S3**
   - Search for "S3" in the top search bar
   - Click on "S3" service

3. **Create Bucket**
   - Click "Create bucket" button
   - **Bucket name:** `smartcoach-backups` (or your preferred name)
   - **Region:** `us-east-1` (or your preferred region)
   - **Object Ownership:** ACLs disabled (recommended)
   - **Block Public Access:** Keep all settings enabled (default)
   - **Bucket Versioning:** Disable (optional, saves costs)
   - **Default encryption:** Enable (recommended)
     - Choose "Amazon S3 managed keys (SSE-S3)"
   - Click "Create bucket"

### Option B: Using AWS CLI

```bash
# Configure AWS credentials first (see Step 4)
aws configure

# Create bucket
aws s3 mb s3://smartcoach-backups --region us-east-1

# Verify bucket was created
aws s3 ls
```

---

## Step 4: Create IAM User for Backups

You need an IAM user with S3 access for the backup script.

### Using AWS Console:

1. **Navigate to IAM**
   - Go to AWS Console
   - Search for "IAM" in the top search bar
   - Click on "IAM" service

2. **Create User**
   - Click "Users" in the left sidebar
   - Click "Create user"
   - **User name:** `smartcoach-backups`
   - Click "Next"

3. **Set Permissions**
   - Select "Attach policies directly"
   - Search for and select: `AmazonS3FullAccess`
   - **OR** (More secure) Create a custom policy:
     - Click "Create policy"
     - Switch to JSON tab
     - Paste this policy:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": [
             "s3:PutObject",
             "s3:GetObject",
             "s3:ListBucket",
             "s3:DeleteObject"
           ],
           "Resource": [
             "arn:aws:s3:::smartcoach-backups",
             "arn:aws:s3:::smartcoach-backups/*"
           ]
         }
       ]
     }
     ```
     - Name it: `SmartCoachBackupPolicy`
     - Create policy
     - Go back to user creation and attach this policy

4. **Create User**
   - Click "Next" → "Create user"

5. **Save Access Keys**
   - Click on the user you just created
   - Go to "Security credentials" tab
   - Click "Create access key"
   - Select "Application running outside AWS"
   - Click "Next" → "Create access key"
   - **IMPORTANT:** Copy both:
     - **Access key ID** (e.g., `AKIAIOSFODNN7EXAMPLE`)
     - **Secret access key** (e.g., `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`)
   - **Save these securely** - you won't be able to see the secret key again!

---

## Step 5: Configure AWS CLI (If Using CLI)

```bash
aws configure
```

You'll be prompted for:
- **AWS Access Key ID:** [Paste your access key ID]
- **AWS Secret Access Key:** [Paste your secret access key]
- **Default region name:** `us-east-1` (or your bucket region)
- **Default output format:** `json` (or `text`)

---

## Step 6: Test S3 Access

### Test with AWS CLI:

```bash
# List buckets (should show your bucket)
aws s3 ls

# List contents of your bucket (should be empty initially)
aws s3 ls s3://smartcoach-backups/

# Test upload (create a test file)
echo "test" > test.txt
aws s3 cp test.txt s3://smartcoach-backups/test.txt

# Verify upload
aws s3 ls s3://smartcoach-backups/

# Clean up test file
aws s3 rm s3://smartcoach-backups/test.txt
rm test.txt
```

### Test with Python Script:

```bash
# Set environment variables
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export BACKUP_S3_BUCKET="smartcoach-backups"
export BACKUP_S3_REGION="us-east-1"

# Test backup script (will create a test backup)
python scripts/backup_database.py --storage s3
```

---

## Step 7: Set Up GitHub Secrets

Now that you have your AWS credentials, add them to GitHub:

1. **Go to GitHub Repository**
   - Navigate to your repository on GitHub
   - Click "Settings" tab

2. **Add Secrets**
   - Click "Secrets and variables" → "Actions"
   - Click "New repository secret"
   - Add these secrets one by one:

   **Secret 1:**
   - **Name:** `AWS_ACCESS_KEY_ID`
   - **Value:** [Your AWS Access Key ID]
   - Click "Add secret"

   **Secret 2:**
   - **Name:** `AWS_SECRET_ACCESS_KEY`
   - **Value:** [Your AWS Secret Access Key]
   - Click "Add secret"

   **Secret 3:**
   - **Name:** `BACKUP_S3_BUCKET`
   - **Value:** `smartcoach-backups` (or your bucket name)
   - Click "Add secret"

   **Secret 4:**
   - **Name:** `BACKUP_S3_REGION`
   - **Value:** `us-east-1` (or your bucket region)
   - Click "Add secret"

   **Secret 5:**
   - **Name:** `BACKUP_STORAGE_TYPE`
   - **Value:** `s3`
   - Click "Add secret"

   **Secret 6:**
   - **Name:** `DATABASE_URL`
   - **Value:** [Your Railway production DATABASE_URL]
   - Click "Add secret"

---

## Step 8: Verify Setup

1. **Check GitHub Secrets**
   - Go to: Repository → Settings → Secrets and variables → Actions
   - Verify all 6 secrets are listed

2. **Test GitHub Actions Workflow**
   - Go to: Repository → Actions tab
   - Select "Database Backup" workflow
   - Click "Run workflow" → "Run workflow"
   - Watch the workflow run
   - Check if backup appears in S3:
     ```bash
     aws s3 ls s3://smartcoach-backups/backups/
     ```

---

## Troubleshooting

### "Access Denied" Error

- Check IAM user has correct permissions
- Verify bucket name matches exactly
- Ensure access keys are correct

### "Bucket Not Found" Error

- Verify bucket name is correct
- Check region matches bucket region
- Ensure bucket exists in your AWS account

### "Invalid Credentials" Error

- Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are correct
- Check if access keys are active (not deactivated)
- Ensure IAM user has S3 permissions

### GitHub Actions Fails

- Check workflow logs for specific error
- Verify all secrets are set correctly
- Ensure DATABASE_URL is accessible from GitHub Actions
- Check if Railway allows external connections

---

## Cost Estimation

**Free Tier (First 12 Months):**
- 5 GB storage: **FREE**
- 20,000 GET requests: **FREE**
- 2,000 PUT requests: **FREE**

**After Free Tier (Typical Usage):**
- Storage: $0.023/GB/month
- PUT requests: $0.005 per 1,000 requests
- GET requests: $0.0004 per 1,000 requests

**Example (10 GB database, daily backups):**
- Storage: 10 GB × $0.023 = **$0.23/month**
- PUT requests: 30 backups × $0.005/1000 = **$0.00015/month**
- **Total: ~$0.23/month**

---

## Security Best Practices

1. ✅ **Use IAM user** (not root account credentials)
2. ✅ **Limit permissions** to specific bucket only
3. ✅ **Enable encryption** on S3 bucket
4. ✅ **Rotate access keys** every 90 days
5. ✅ **Never commit** access keys to Git
6. ✅ **Use GitHub Secrets** for credentials
7. ✅ **Enable MFA** on AWS account

---

## Next Steps

Once S3 is set up:

1. ✅ Test backup manually: `python scripts/backup_database.py`
2. ✅ Test restore: `python scripts/restore_database.py --latest`
3. ✅ Verify GitHub Actions workflow runs successfully
4. ✅ Monitor backup storage usage in AWS Console

For more information, see:
- `docs/DISASTER_RECOVERY_PLAN.md` - Full DR procedures
- `scripts/BACKUP_SETUP.md` - Backup script usage

