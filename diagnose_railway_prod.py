#!/usr/bin/env python3
"""
Run diagnostics against Railway production database.

This script uses Railway CLI to get the production DATABASE_URL.

Usage:
    python diagnose_railway_prod.py andres.tellez@gmail.com
    python diagnose_railway_prod.py 347085
"""

import os
import sys
import subprocess
import json


def get_railway_db_url():
    """Get DATABASE_URL from Railway using Railway CLI."""
    try:
        # Try to get DATABASE_URL from Railway
        result = subprocess.run(
            ["railway", "variables", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )

        variables = json.loads(result.stdout)

        # Look for DATABASE_URL
        for var in variables:
            if var.get("key") == "DATABASE_URL":
                return var.get("value")

        print("⚠️  DATABASE_URL not found in Railway variables")
        print("   Available variables:")
        for var in variables:
            print(f"     {var.get('key')}")
        return None

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get Railway variables: {e}")
        print("   Make sure Railway CLI is installed and you're logged in:")
        print("   npm i -g @railway/cli")
        print("   railway login")
        return None
    except FileNotFoundError:
        print("❌ Railway CLI not found!")
        print("   Install it: npm i -g @railway/cli")
        print("   Or manually set PROD_DATABASE_URL environment variable")
        return None
    except json.JSONDecodeError:
        print("❌ Failed to parse Railway output")
        return None


def main():
    # Try to get DATABASE_URL from Railway
    db_url = get_railway_db_url()

    if not db_url:
        print("\n💡 Alternative: Set PROD_DATABASE_URL manually:")
        print("   export PROD_DATABASE_URL='postgres://...'")
        print("   python diagnose_missing_activity.py andres.tellez@gmail.com")
        sys.exit(1)

    # Set it before importing db_session
    os.environ["DATABASE_URL"] = db_url

    print(f"✅ Got DATABASE_URL from Railway")
    print(f"   Database: {db_url[:50]}...")
    print()

    # Now run the diagnostic
    # We need to set DATABASE_URL before importing, so we'll exec the script
    # But first, let's modify sys.argv to pass through the arguments
    original_argv = sys.argv
    sys.argv = ["diagnose_missing_activity.py"] + original_argv[1:]

    # Import and run
    import diagnose_missing_activity

    diagnose_missing_activity.main()


if __name__ == "__main__":
    main()
