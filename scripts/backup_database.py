#!/usr/bin/env python3
"""
Automated Database Backup Script

Creates a PostgreSQL database backup and uploads it to cloud storage.
Designed to run via GitHub Actions or manually.

Usage:
    python scripts/backup_database.py
    python scripts/backup_database.py --storage s3 --bucket my-bucket
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_database_url():
    """Get DATABASE_URL from environment."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Set it in Railway or export it before running this script."
        )
    return db_url


def create_backup(db_url: str, output_file: str) -> bool:
    """
    Create PostgreSQL backup using pg_dump.
    
    Args:
        db_url: PostgreSQL connection URL
        output_file: Path to output SQL file
        
    Returns:
        True if backup successful, False otherwise
    """
    print(f"📦 Creating database backup: {output_file}")
    
    try:
        # Run pg_dump
        result = subprocess.run(
            [
                "pg_dump",
                "--no-owner",  # Don't output commands to set ownership
                "--no-acl",    # Don't output access privileges
                "--clean",     # Include DROP statements
                "--if-exists", # Use IF EXISTS for DROP statements
                "-f", output_file,
                db_url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        
        # Check file was created and has content
        backup_path = Path(output_file)
        if not backup_path.exists():
            print(f"❌ Backup file was not created: {output_file}")
            return False
            
        file_size = backup_path.stat().st_size
        if file_size == 0:
            print(f"❌ Backup file is empty: {output_file}")
            return False
            
        print(f"✅ Backup created successfully: {output_file} ({file_size:,} bytes)")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ pg_dump failed: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ pg_dump not found. Install PostgreSQL client tools.")
        return False


def upload_to_s3(file_path: str, bucket: str, region: str = "us-east-1") -> bool:
    """
    Upload backup file to AWS S3.
    
    Args:
        file_path: Path to backup file
        bucket: S3 bucket name
        region: AWS region
        
    Returns:
        True if upload successful, False otherwise
    """
    try:
        import boto3
    except ImportError:
        print("❌ boto3 not installed. Install with: pip install boto3")
        return False
    
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if not access_key or not secret_key:
        print("❌ AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return False
    
    print(f"☁️  Uploading to S3: s3://{bucket}/backups/{Path(file_path).name}")
    
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        
        s3_key = f"backups/{Path(file_path).name}"
        s3_client.upload_file(file_path, bucket, s3_key)
        
        print(f"✅ Upload successful: s3://{bucket}/{s3_key}")
        return True
        
    except Exception as e:
        print(f"❌ S3 upload failed: {e}")
        return False


def upload_to_b2(file_path: str, bucket_name: str) -> bool:
    """
    Upload backup file to Backblaze B2.
    
    Args:
        file_path: Path to backup file
        bucket_name: B2 bucket name
        
    Returns:
        True if upload successful, False otherwise
    """
    try:
        from b2sdk.v1 import InMemoryAccountInfo, B2Api
        from b2sdk.v1.exception import B2Error
    except ImportError:
        print("❌ b2sdk not installed. Install with: pip install b2sdk")
        return False
    
    application_key_id = os.getenv("B2_APPLICATION_KEY_ID")
    application_key = os.getenv("B2_APPLICATION_KEY")
    
    if not application_key_id or not application_key:
        print("❌ B2 credentials not found. Set B2_APPLICATION_KEY_ID and B2_APPLICATION_KEY")
        return False
    
    print(f"☁️  Uploading to Backblaze B2: {bucket_name}/{Path(file_path).name}")
    
    try:
        # Initialize B2 API
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account("production", application_key_id, application_key)
        
        # Get bucket
        bucket = b2_api.get_bucket_by_name(bucket_name)
        
        # Upload file
        file_name = f"backups/{Path(file_path).name}"
        uploaded_file = bucket.upload_local_file(
            local_file=file_path,
            file_name=file_name,
        )
        
        print(f"✅ Upload successful: {bucket_name}/{file_name}")
        print(f"   File ID: {uploaded_file.id_}")
        return True
        
    except B2Error as e:
        print(f"❌ B2 upload failed: {e}")
        return False
    except Exception as e:
        print(f"❌ B2 upload failed: {e}")
        return False


def upload_to_local_storage(file_path: str, storage_path: str) -> bool:
    """
    Copy backup file to local storage directory.
    
    Args:
        file_path: Path to backup file
        storage_path: Directory to store backups
        
    Returns:
        True if copy successful, False otherwise
    """
    storage_dir = Path(storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    dest_file = storage_dir / Path(file_path).name
    
    try:
        import shutil
        shutil.copy2(file_path, dest_file)
        print(f"✅ Copied to local storage: {dest_file}")
        return True
    except Exception as e:
        print(f"❌ Local storage copy failed: {e}")
        return False


def cleanup_old_backups_b2(bucket_name: str, retention_days: int = 7) -> None:
    """
    Delete old backups from Backblaze B2 based on retention policy.
    
    Args:
        bucket_name: B2 bucket name
        retention_days: Number of days to keep backups
    """
    try:
        from b2sdk.v1 import InMemoryAccountInfo, B2Api
        from b2sdk.v1.exception import B2Error
        from datetime import timedelta
        
        application_key_id = os.getenv("B2_APPLICATION_KEY_ID")
        application_key = os.getenv("B2_APPLICATION_KEY")
        
        if not application_key_id or not application_key:
            print("⚠️  Cannot cleanup old backups: B2 credentials not found")
            return
        
        # Initialize B2 API
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account("production", application_key_id, application_key)
        
        # Get bucket
        bucket = b2_api.get_bucket_by_name(bucket_name)
        
        # List files in backups/ prefix
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        deleted_count = 0
        for file_info, folder_name in bucket.ls(folder_to_list="backups/", recursive=True):
            if file_info.file_name.endswith(".sql"):
                # Parse timestamp from filename (backup_YYYYMMDD_HHMMSS.sql)
                try:
                    filename = Path(file_info.file_name).name
                    if filename.startswith("backup_") and len(filename) > 20:
                        date_str = filename[7:15]  # Extract YYYYMMDD
                        file_date = datetime.strptime(date_str, "%Y%m%d")
                        
                        if file_date < cutoff_date.date():
                            bucket.delete_file_version(file_info.id_, file_info.file_name)
                            deleted_count += 1
                            print(f"🗑️  Deleted old backup: {filename}")
                except (ValueError, IndexError):
                    # If we can't parse date, skip it
                    continue
        
        if deleted_count > 0:
            print(f"✅ Cleaned up {deleted_count} old backup(s) from B2")
        else:
            print("ℹ️  No old backups to cleanup in B2")
            
    except Exception as e:
        print(f"⚠️  B2 cleanup failed (non-critical): {e}")


def cleanup_old_backups_s3(bucket: str, region: str, retention_days: int = 7) -> None:
    """
    Delete old backups from S3 based on retention policy.
    
    Args:
        bucket: S3 bucket name
        region: AWS region
        retention_days: Number of days to keep backups
    """
    try:
        import boto3
        from datetime import timedelta
        
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        
        if not access_key or not secret_key:
            print("⚠️  Cannot cleanup old backups: AWS credentials not found")
            return
        
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # List all backups
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix="backups/")
        
        if "Contents" not in response:
            print("ℹ️  No backups found to cleanup")
            return
        
        deleted_count = 0
        for obj in response["Contents"]:
            key = obj["Key"]
            last_modified = obj["LastModified"].replace(tzinfo=None)
            
            if last_modified < cutoff_date:
                s3_client.delete_object(Bucket=bucket, Key=key)
                deleted_count += 1
                print(f"🗑️  Deleted old backup: {key}")
        
        if deleted_count > 0:
            print(f"✅ Cleaned up {deleted_count} old backup(s)")
        else:
            print("ℹ️  No old backups to cleanup")
            
    except Exception as e:
        print(f"⚠️  Cleanup failed (non-critical): {e}")


def main():
    """Main backup function."""
    parser = argparse.ArgumentParser(description="Backup PostgreSQL database")
    parser.add_argument(
        "--storage",
        choices=["s3", "b2", "local"],
        default=os.getenv("BACKUP_STORAGE_TYPE", "b2"),
        help="Storage type (s3, b2, or local)",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("B2_BUCKET_NAME", os.getenv("BACKUP_S3_BUCKET", "smartcoach-backups")),
        help="Bucket name (B2 bucket name for b2 storage, S3 bucket for s3 storage)",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("BACKUP_S3_REGION", "us-east-1"),
        help="AWS region (for s3 storage)",
    )
    parser.add_argument(
        "--local-path",
        default=os.getenv("BACKUP_LOCAL_PATH", "./backups"),
        help="Local storage path (for local storage)",
    )
    parser.add_argument(
        "--output-dir",
        default="./backups",
        help="Temporary directory for backup file",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=7,
        help="Number of days to keep backups",
    )
    
    args = parser.parse_args()
    
    # Get database URL
    try:
        db_url = get_database_url()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = output_dir / f"backup_{timestamp}.sql"
    
    # Create backup
    if not create_backup(db_url, str(backup_file)):
        print("❌ Backup creation failed")
        sys.exit(1)
    
    # Upload to storage
    upload_success = False
    if args.storage == "s3":
        upload_success = upload_to_s3(str(backup_file), args.bucket, args.region)
        if upload_success:
            cleanup_old_backups_s3(args.bucket, args.region, args.retention_days)
    elif args.storage == "b2":
        b2_bucket = os.getenv("B2_BUCKET_NAME", args.bucket)
        upload_success = upload_to_b2(str(backup_file), b2_bucket)
        if upload_success:
            cleanup_old_backups_b2(b2_bucket, args.retention_days)
    elif args.storage == "local":
        upload_success = upload_to_local_storage(str(backup_file), args.local_path)
    
    if not upload_success:
        print("⚠️  Backup created but upload failed. File saved locally.")
        print(f"   Local file: {backup_file}")
        sys.exit(1)
    
    # Clean up local file if upload successful
    try:
        backup_file.unlink()
        print(f"🧹 Cleaned up local backup file")
    except Exception as e:
        print(f"⚠️  Could not delete local file (non-critical): {e}")
    
    print("✅ Backup process completed successfully")


if __name__ == "__main__":
    main()

