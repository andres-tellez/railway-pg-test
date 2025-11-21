# Incremental Migration Guide

## Overview

The migration process can now run in **incremental/delta mode**, which only copies new or updated records since the last migration. This makes subsequent runs much faster and reduces database load.

## How It Works

1. **Tracks Last Migration Timestamp**: Creates a `migration_log` table in local database to track when each table was last synced
2. **Delta Queries**: Only fetches records from production that were created/updated after the last migration timestamp
3. **Updates Log**: After successful migration, updates the timestamp for that table

## Usage

### Option 1: Use the New Incremental Script (Recommended)

```bash
# Incremental mode (default - only new/updated records)
python scripts/migrate_prod_to_local_incremental.py

# Full migration (ignore last timestamp, copy everything)
python scripts/migrate_prod_to_local_incremental.py --full
```

### Option 2: Modify Original Script

Add incremental support to `scripts/migrate_prod_to_local.py`:

**Key Changes Needed:**

1. **Add migration_log table** to track timestamps
2. **Modify queries** to filter by last_migration_timestamp
3. **Update log** after successful migration

## Implementation Details

### Migration Log Table

The script automatically creates a `migration_log` table:

```sql
CREATE TABLE migration_log (
    table_name VARCHAR(255) PRIMARY KEY,
    last_migration_timestamp TIMESTAMP WITH TIME ZONE,
    record_count INTEGER DEFAULT 0,
    last_migration_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
)
```

### Tables with Incremental Support

Currently implemented for:
- ✅ **activities** - Uses `start_date` field

Can be extended to:
- **plans** - Use `created_at` or `updated_at`
- **conversations** - Use `created_at` or `updated_at`
- **splits** - Migrated when parent activity migrates (automatic)
- **plan_workouts** - Migrated when parent plan migrates (automatic)

### Tables That Always Sync Fully

These tables are small or don't have reliable timestamps:
- `user_identity` - Small, always sync
- `user_athletes` - Small, always sync
- `user_profile` - Small, always sync (or check `updated_at` if added)

## Benefits

1. **Faster Migrations**: Only copies new/updated data
2. **Reduced Load**: Less data transferred, faster queries
3. **Safe to Run Often**: Can run daily/hourly without performance impact
4. **Automatic Tracking**: No manual timestamp management needed

## Example Output

```
🔄 INCREMENTAL migration mode (only new/updated records)

📋 Migrating activities (incremental)...
   🔄 Incremental mode: Only fetching activities after 2025-11-20T10:30:00
   Found 5 new/updated activities to migrate
✅ Migrated 5 activities
```

## First Run

The first run will behave like a full migration (no previous timestamp exists):
- Creates `migration_log` table
- Copies all data
- Records timestamp for next run

## Manual Reset

To reset and force full migration:

```sql
-- In LOCAL database
DELETE FROM migration_log WHERE table_name = 'activities';
-- Or delete all logs
TRUNCATE TABLE migration_log;
```

## Extending to Other Tables

To add incremental support for other tables:

1. Add timestamp filtering to the migrate method
2. Update migration_log after success
3. Use appropriate timestamp field (`created_at`, `updated_at`, etc.)

Example pattern:

```python
last_timestamp = self.get_last_migration_timestamp("table_name")
if last_timestamp:
    query = text("SELECT * FROM table_name WHERE updated_at > :timestamp")
    params = {"timestamp": last_timestamp}
else:
    query = text("SELECT * FROM table_name")
    params = {}
```
