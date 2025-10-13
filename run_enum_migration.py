#!/usr/bin/env python3
"""Run the enum case migration SQL directly"""

import os
import psycopg2
from urllib.parse import urlparse

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment")
    exit(1)

# Parse the database URL
parsed = urlparse(DATABASE_URL)
db_config = {
    'host': parsed.hostname,
    'port': parsed.port,
    'database': parsed.path[1:],  # Remove leading slash
    'user': parsed.username,
    'password': parsed.password,
    'sslmode': 'require'
}

print("🔧 Connecting to database...")
print(f"   Host: {db_config['host']}")
print(f"   Database: {db_config['database']}\n")

try:
    # Connect to database
    conn = psycopg2.connect(**db_config)
    conn.autocommit = True  # Required for DDL statements
    cur = conn.cursor()
    
    # Step 1: Convert column to varchar
    print("📝 Step 1: Converting status column to VARCHAR...")
    cur.execute("ALTER TABLE webhook_events ALTER COLUMN status TYPE VARCHAR(20)")
    print("✅ Done")
    
    # Step 2: Drop old enum
    print("\n📝 Step 2: Dropping old enum type...")
    cur.execute("DROP TYPE webhookeventstatus")
    print("✅ Done")
    
    # Step 3: Create new enum with uppercase values
    print("\n📝 Step 3: Creating new enum with uppercase values...")
    cur.execute("""
        CREATE TYPE webhookeventstatus AS ENUM (
            'PENDING',
            'PROCESSING', 
            'COMPLETED',
            'FAILED',
            'IGNORED'
        )
    """)
    print("✅ Done")
    
    # Step 4: Update existing data (if any)
    print("\n📝 Step 4: Updating existing data to uppercase...")
    cur.execute("""
        UPDATE webhook_events 
        SET status = UPPER(status)
        WHERE status IN ('pending', 'processing', 'completed', 'failed', 'ignored')
    """)
    print(f"✅ Done (updated {cur.rowcount} rows)")
    
    # Step 5: Convert column back to enum
    print("\n📝 Step 5: Converting status column back to enum...")
    cur.execute("""
        ALTER TABLE webhook_events 
        ALTER COLUMN status TYPE webhookeventstatus 
        USING status::webhookeventstatus
    """)
    print("✅ Done")
    
    # Verify the enum values
    print("\n🔍 Verifying new enum values...")
    cur.execute("""
        SELECT enumlabel 
        FROM pg_enum 
        WHERE enumtypid = (
            SELECT oid 
            FROM pg_type 
            WHERE typname = 'webhookeventstatus'
        )
        ORDER BY enumsortorder;
    """)
    
    enum_values = cur.fetchall()
    print("   Enum values:")
    for value in enum_values:
        print(f"     - '{value[0]}'")
    
    cur.close()
    conn.close()
    
    print("\n🎉 Migration completed successfully!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    exit(1)

