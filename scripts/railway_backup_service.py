#!/usr/bin/env python3
"""
Railway Backup Service

Simple backup service designed to run on Railway.
Creates database backups and stores them in a mounted Railway Volume.

Usage:
    python scripts/railway_backup_service.py

Environment Variables:
    DATABASE_URL - PostgreSQL connection URL (required)
    BACKUP_LOCAL_PATH - Path to backup directory (default: /backups)
    BACKUP_RETENTION_DAYS - Days to keep backups (default: 7)
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_database_url():
    """Get DATABASE_URL from environment."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Set it in Railway environment variables."
        )
    return db_url


def create_backup(db_url: str, backup_path: str) -> str:
    """
    Create PostgreSQL backup.

    Args:
        db_url: PostgreSQL connection URL
        backup_path: Directory to store backup

    Returns:
        Path to created backup file
    """
    # Ensure backup directory exists
    backup_dir = Path(backup_path)
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate backup filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"backup_{timestamp}.sql"

    print(f"📦 Creating database backup: {backup_file}")

    try:
        # Run pg_dump
        result = subprocess.run(
            [
                "pg_dump",
                "--no-owner",  # Don't output commands to set ownership
                "--no-acl",  # Don't output access privileges
                "--clean",  # Include DROP statements
                "--if-exists",  # Use IF EXISTS for DROP statements
                "-f",
                str(backup_file),
                db_url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Verify backup was created
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file was not created: {backup_file}")

        file_size = backup_file.stat().st_size
        if file_size == 0:
            raise ValueError(f"Backup file is empty: {backup_file}")

        print(f"✅ Backup created successfully: {backup_file} ({file_size:,} bytes)")
        return str(backup_file)

    except subprocess.CalledProcessError as e:
        print(f"❌ pg_dump failed: {e}")
        print(f"Error output: {e.stderr}")
        raise
    except FileNotFoundError:
        print("❌ pg_dump not found. Install PostgreSQL client tools.")
        raise


def cleanup_old_backups(backup_path: str, retention_days: int) -> int:
    """
    Delete backups older than retention period.

    Args:
        backup_path: Directory containing backups
        retention_days: Number of days to keep backups

    Returns:
        Number of backups deleted
    """
    backup_dir = Path(backup_path)
    if not backup_dir.exists():
        print("ℹ️  Backup directory does not exist, skipping cleanup")
        return 0

    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    deleted_count = 0

    print(
        f"🧹 Cleaning up backups older than {retention_days} days (before {cutoff_date.date()})"
    )

    for backup_file in backup_dir.glob("backup_*.sql"):
        try:
            # Get file modification time
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)

            if file_time < cutoff_date:
                file_size = backup_file.stat().st_size
                backup_file.unlink()
                deleted_count += 1
                print(
                    f"  🗑️  Deleted: {backup_file.name} ({file_size:,} bytes, {file_time.date()})"
                )
        except Exception as e:
            print(f"  ⚠️  Could not delete {backup_file.name}: {e}")

    if deleted_count > 0:
        print(f"✅ Cleaned up {deleted_count} old backup(s)")
    else:
        print("ℹ️  No old backups to cleanup")

    return deleted_count


def list_backups(backup_path: str) -> list:
    """
    List all backups in the backup directory.

    Args:
        backup_path: Directory containing backups

    Returns:
        List of backup file paths
    """
    backup_dir = Path(backup_path)
    if not backup_dir.exists():
        return []

    backups = sorted(backup_dir.glob("backup_*.sql"), reverse=True)
    return [str(b) for b in backups]


def main():
    """Main backup function."""
    # Get configuration from environment
    db_url = get_database_url()
    backup_path = os.getenv("BACKUP_LOCAL_PATH", "/backups")
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))

    print("=" * 60)
    print("Railway Database Backup Service")
    print("=" * 60)
    print(f"Backup path: {backup_path}")
    print(f"Retention: {retention_days} days")
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else 'hidden'}")
    print("=" * 60)
    print()

    try:
        # Create backup
        backup_file = create_backup(db_url, backup_path)

        # Cleanup old backups
        cleanup_old_backups(backup_path, retention_days)

        # List current backups
        backups = list_backups(backup_path)
        print()
        print(f"📋 Current backups ({len(backups)} total):")
        for backup in backups[:5]:  # Show last 5
            backup_path_obj = Path(backup)
            size = backup_path_obj.stat().st_size
            mtime = datetime.fromtimestamp(backup_path_obj.stat().st_mtime)
            print(
                f"  • {backup_path_obj.name} ({size:,} bytes, {mtime.strftime('%Y-%m-%d %H:%M:%S')})"
            )
        if len(backups) > 5:
            print(f"  ... and {len(backups) - 5} more")

        print()
        print("✅ Backup process completed successfully")
        return 0

    except Exception as e:
        print()
        print(f"❌ Backup failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

