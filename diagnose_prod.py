#!/usr/bin/env python3
"""
Quick script to run diagnostics against production database.

Usage:
    python diagnose_prod.py [email_or_athlete_id]

Example:
    python diagnose_prod.py andres.tellez@gmail.com
    python diagnose_prod.py 347085
"""

import os
import sys

# Set production database URL here or via environment variable
PROD_DB_URL = os.getenv("PROD_DATABASE_URL") or os.getenv("DATABASE_URL_PROD")

if not PROD_DB_URL:
    print("❌ PROD_DATABASE_URL not set!")
    print("\nSet it via:")
    print("  1. Environment variable: export PROD_DATABASE_URL='postgres://...'")
    print("  2. Or edit this script and set PROD_DB_URL directly")
    print("\nTo get your Railway production database URL:")
    print("  railway variables --service <your-service-name>")
    sys.exit(1)

# Set the database URL before importing db_session
os.environ["DATABASE_URL"] = PROD_DB_URL

# Now import and run the diagnostic
from diagnose_missing_activity import main

if __name__ == "__main__":
    print(f"🔍 Connecting to PRODUCTION database...")
    print(f"   Database: {PROD_DB_URL[:50]}...")
    print()
    main()
