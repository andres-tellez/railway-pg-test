#!/usr/bin/env python3
"""Check what values are actually in the database enum"""

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
}

try:
    # Connect to database
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    
    # Check what values are in the enum
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
    print("🔍 Database enum values:")
    for value in enum_values:
        print(f"  - '{value[0]}'")
    
    # Also check the table structure
    cur.execute("""
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns 
        WHERE table_name = 'webhook_events' 
        AND column_name = 'status';
    """)
    
    column_info = cur.fetchone()
    if column_info:
        print(f"\n📋 Status column info:")
        print(f"  - Column: {column_info[0]}")
        print(f"  - Data type: {column_info[1]}")
        print(f"  - UDT name: {column_info[2]}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
