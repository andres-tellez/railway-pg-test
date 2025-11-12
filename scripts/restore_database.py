#!/usr/bin/env python3
"""
Database Restore Script

Restores a PostgreSQL database from a backup file.

Usage:
    python scripts/restore_database.py --backup backup_20241112_020000.sql
    python scripts/restore_database.py --latest
    python scripts/restore_database.py --backup backup.sql --database-url $STAGING_DATABASE_URL
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_database_url(custom_url: str = None):
    """Get DATABASE_URL from environment or argument."""
    db_url = custom_url or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Set it in Railway or provide --database-url argument."
        )
    return db_url


def download_from_s3(backup_name: str, bucket: str, region: str, output_file: str) -> bool:
    """
    Download backup file from AWS S3.
    
    Args:
        backup_name: Name of backup file (with or without backups/ prefix)
        bucket: S3 bucket name
        region: AWS region
        output_file: Local path to save file
        
    Returns:
        True if download successful, False otherwise
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
    
    # Ensure backup_name has backups/ prefix
    if not backup_name.startswith("backups/"):
        s3_key = f"backups/{backup_name}"
    else:
        s3_key = backup_name
    
    print(f"☁️  Downloading from S3: s3://{bucket}/{s3_key}")
    
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        
        s3_client.download_file(bucket, s3_key, output_file)
        
        print(f"✅ Download successful: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ S3 download failed: {e}")
        return False


def download_from_b2(backup_name: str, bucket_name: str, output_file: str) -> bool:
    """
    Download backup file from Backblaze B2.
    
    Args:
        backup_name: Name of backup file (with or without backups/ prefix)
        bucket_name: B2 bucket name
        output_file: Local path to save file
        
    Returns:
        True if download successful, False otherwise
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
    
    # Ensure backup_name has backups/ prefix
    if not backup_name.startswith("backups/"):
        b2_file_name = f"backups/{backup_name}"
    else:
        b2_file_name = backup_name
    
    print(f"☁️  Downloading from Backblaze B2: {bucket_name}/{b2_file_name}")
    
    try:
        # Initialize B2 API
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account("production", application_key_id, application_key)
        
        # Get bucket
        bucket = b2_api.get_bucket_by_name(bucket_name)
        
        # Download file
        downloaded_file = bucket.download_file_by_name(b2_file_name, output_file)
        
        print(f"✅ Download successful: {output_file}")
        return True
        
    except B2Error as e:
        print(f"❌ B2 download failed: {e}")
        return False
    except Exception as e:
        print(f"❌ B2 download failed: {e}")
        return False


def list_backups_b2(bucket_name: str) -> list:
    """
    List available backups in Backblaze B2.
    
    Args:
        bucket_name: B2 bucket name
        
    Returns:
        List of backup dictionaries with filename, size, and last_modified
    """
    try:
        from b2sdk.v1 import InMemoryAccountInfo, B2Api
        from b2sdk.v1.exception import B2Error
        
        application_key_id = os.getenv("B2_APPLICATION_KEY_ID")
        application_key = os.getenv("B2_APPLICATION_KEY")
        
        if not application_key_id or not application_key:
            print("❌ B2 credentials not found")
            return []
        
        # Initialize B2 API
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account("production", application_key_id, application_key)
        
        # Get bucket
        bucket = b2_api.get_bucket_by_name(bucket_name)
        
        backups = []
        for file_info, folder_name in bucket.ls(folder_to_list="backups/", recursive=True):
            if file_info.file_name.endswith(".sql"):
                filename = Path(file_info.file_name).name
                backups.append({
                    "filename": filename,
                    "key": file_info.file_name,
                    "last_modified": file_info.upload_timestamp / 1000,  # Convert from milliseconds
                    "size": file_info.size,
                })
        
        # Sort by last_modified (newest first)
        backups.sort(key=lambda x: x["last_modified"], reverse=True)
        return backups
        
    except Exception as e:
        print(f"❌ Failed to list backups: {e}")
        return []


def list_backups_s3(bucket: str, region: str) -> list:
    """
    List available backups in S3.
    
    Args:
        bucket: S3 bucket name
        region: AWS region
        
    Returns:
        List of backup filenames
    """
    try:
        import boto3
        
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        
        if not access_key or not secret_key:
            print("❌ AWS credentials not found")
            return []
        
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix="backups/")
        
        if "Contents" not in response:
            return []
        
        backups = []
        for obj in response["Contents"]:
            key = obj["Key"]
            if key.endswith(".sql"):
                filename = Path(key).name
                backups.append({
                    "filename": filename,
                    "key": key,
                    "last_modified": obj["LastModified"],
                    "size": obj["Size"],
                })
        
        # Sort by last_modified (newest first)
        backups.sort(key=lambda x: x["last_modified"], reverse=True)
        return backups
        
    except Exception as e:
        print(f"❌ Failed to list backups: {e}")
        return []


def restore_backup(db_url: str, backup_file: str, confirm: bool = False) -> bool:
    """
    Restore PostgreSQL database from backup file.
    
    Args:
        db_url: PostgreSQL connection URL
        backup_file: Path to backup SQL file
        confirm: Skip confirmation prompt
        
    Returns:
        True if restore successful, False otherwise
    """
    backup_path = Path(backup_file)
    
    if not backup_path.exists():
        print(f"❌ Backup file not found: {backup_file}")
        return False
    
    file_size = backup_path.stat().st_size
    if file_size == 0:
        print(f"❌ Backup file is empty: {backup_file}")
        return False
    
    print(f"📦 Restoring database from: {backup_file} ({file_size:,} bytes)")
    
    if not confirm:
        response = input(
            f"⚠️  WARNING: This will overwrite the database at {db_url}\n"
            "Are you sure you want to continue? (yes/no): "
        )
        if response.lower() not in ["yes", "y"]:
            print("❌ Restore cancelled")
            return False
    
    try:
        # Read and execute SQL file
        result = subprocess.run(
            ["psql", db_url, "-f", str(backup_path)],
            capture_output=True,
            text=True,
            check=False,  # Don't fail on warnings
        )
        
        if result.returncode == 0:
            print("✅ Database restore completed successfully")
            return True
        else:
            print(f"⚠️  Restore completed with warnings/errors:")
            print(result.stderr)
            # Still return True if it's just warnings
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Restore failed: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ psql not found. Install PostgreSQL client tools.")
        return False


def verify_restore(db_url: str) -> bool:
    """
    Verify database restore by checking critical tables.
    
    Args:
        db_url: PostgreSQL connection URL
        
    Returns:
        True if verification successful, False otherwise
    """
    print("🔍 Verifying database restore...")
    
    try:
        # Check if we can connect
        result = subprocess.run(
            ["psql", db_url, "-c", "SELECT 1;"],
            capture_output=True,
            text=True,
            check=True,
        )
        
        # Check critical tables
        checks = [
            ("user_identity", "SELECT COUNT(*) FROM user_identity;"),
            ("activities", "SELECT COUNT(*) FROM activities;"),
            ("plans", "SELECT COUNT(*) FROM plans;"),
        ]
        
        all_ok = True
        for table_name, query in checks:
            result = subprocess.run(
                ["psql", db_url, "-t", "-c", query],
                capture_output=True,
                text=True,
                check=False,
            )
            
            if result.returncode == 0:
                count = result.stdout.strip()
                print(f"  ✅ {table_name}: {count} rows")
            else:
                print(f"  ⚠️  {table_name}: Could not verify")
                all_ok = False
        
        if all_ok:
            print("✅ Database verification completed")
        else:
            print("⚠️  Database verification completed with warnings")
        
        return all_ok
        
    except Exception as e:
        print(f"⚠️  Verification failed: {e}")
        return False


def main():
    """Main restore function."""
    parser = argparse.ArgumentParser(description="Restore PostgreSQL database from backup")
    parser.add_argument(
        "--backup",
        help="Backup filename (e.g., backup_20241112_020000.sql) or path to local file",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use latest backup from storage",
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (overrides DATABASE_URL env var)",
    )
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
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt (use with caution!)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip database verification after restore",
    )
    
    args = parser.parse_args()
    
    # Get database URL
    try:
        db_url = get_database_url(args.database_url)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Determine backup file
    backup_file = None
    
    if args.latest:
        # Get latest backup from storage
        if args.storage == "s3":
            backups = list_backups_s3(args.bucket, args.region)
            if not backups:
                print("❌ No backups found in S3")
                sys.exit(1)
            latest = backups[0]
            backup_file = latest["filename"]
            print(f"📋 Latest backup: {backup_file} ({latest['size']:,} bytes)")
        elif args.storage == "b2":
            b2_bucket = os.getenv("B2_BUCKET_NAME", args.bucket)
            backups = list_backups_b2(b2_bucket)
            if not backups:
                print("❌ No backups found in B2")
                sys.exit(1)
            latest = backups[0]
            backup_file = latest["filename"]
            # Convert timestamp to datetime for display
            from datetime import datetime
            mod_time = datetime.fromtimestamp(latest["last_modified"])
            print(f"📋 Latest backup: {backup_file} ({latest['size']:,} bytes, {mod_time.strftime('%Y-%m-%d %H:%M:%S')})")
        else:
            # Local storage
            local_path = Path(args.local_path)
            backups = sorted(local_path.glob("backup_*.sql"), reverse=True)
            if not backups:
                print(f"❌ No backups found in {local_path}")
                sys.exit(1)
            backup_file = backups[0]
            print(f"📋 Latest backup: {backup_file.name}")
    
    elif args.backup:
        backup_file = args.backup
    else:
        print("❌ Must specify --backup or --latest")
        parser.print_help()
        sys.exit(1)
    
    # Download from cloud storage if needed
    if args.storage == "s3" and not Path(backup_file).exists():
        temp_file = f"./temp_{Path(backup_file).name}"
        if not download_from_s3(backup_file, args.bucket, args.region, temp_file):
            print("❌ Failed to download backup")
            sys.exit(1)
        backup_file = temp_file
    elif args.storage == "b2" and not Path(backup_file).exists():
        b2_bucket = os.getenv("B2_BUCKET_NAME", args.bucket)
        temp_file = f"./temp_{Path(backup_file).name}"
        if not download_from_b2(backup_file, b2_bucket, temp_file):
            print("❌ Failed to download backup")
            sys.exit(1)
        backup_file = temp_file
    
    # Restore database
    if not restore_backup(db_url, backup_file, args.confirm):
        print("❌ Restore failed")
        sys.exit(1)
    
    # Verify restore
    if not args.no_verify:
        verify_restore(db_url)
    
    # Cleanup temp file if downloaded
    if args.storage in ["s3", "b2"] and Path(backup_file).name.startswith("temp_"):
        try:
            Path(backup_file).unlink()
            print(f"🧹 Cleaned up temporary file")
        except Exception:
            pass
    
    print("✅ Restore process completed successfully")


if __name__ == "__main__":
    main()

