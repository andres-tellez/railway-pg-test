"""
Quick script to find your user_id from the database.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(".env.local")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    print("[OK] Loaded .env.local")
else:
    print("[WARNING] .env.local not found, using default environment")

sys.path.insert(0, "src")

from src.db.db_session import get_db
from src.db.models.user_identity import UserIdentity


def main():
    db = next(get_db())

    try:
        # Get all users
        users = db.query(UserIdentity).all()

        print("\n" + "=" * 80)
        print("  USERS IN DATABASE")
        print("=" * 80)

        if not users:
            print("\n❌ No users found in database")
            return

        for i, user in enumerate(users, 1):
            print(f"\n{i}. User ID: {user.user_id}")
            print(f"   Email: {user.email if hasattr(user, 'email') else 'N/A'}")
            print(
                f"   Auth0 ID: {user.auth0_user_id if hasattr(user, 'auth0_user_id') else 'N/A'}"
            )

        print("\n" + "=" * 80)
        print(f"\nTotal users: {len(users)}")

        if len(users) == 1:
            print(f"\n✅ Your user_id is: {users[0].user_id}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
