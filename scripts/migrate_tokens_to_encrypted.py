"""
Migration Script: Encrypt Existing Tokens
==========================================

This script migrates existing plain-text tokens to encrypted format.

⚠️  IMPORTANT: Run this AFTER deploying the new Token model with encryption.

Prerequisites:
1. TOKEN_ENCRYPTION_KEY must be set in environment
2. Database must have the new Token model structure (_encrypted_access_token, _encrypted_refresh_token)
3. revoked_at column must exist

Usage:
    python scripts/migrate_tokens_to_encrypted.py

This script:
1. Reads all existing tokens from database
2. Encrypts them using the new encryption system
3. Updates the database with encrypted values
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment
env_local_path = project_root / ".env.local"
if env_local_path.exists():
    load_dotenv(env_local_path, override=False)
    print(f"[OK] Loaded environment from .env.local", flush=True)
else:
    print("[OK] Using system environment variables", flush=True)

from src.db.db_session import get_session
from src.db.models.tokens import Token
from src.utils.token_encryption import encrypt_token


def migrate_tokens():
    """Migrate all existing tokens to encrypted format."""
    session = get_session()
    try:
        # Check if encryption key is set
        if not os.getenv("TOKEN_ENCRYPTION_KEY"):
            print(
                "⚠️  WARNING: TOKEN_ENCRYPTION_KEY not set. Using passphrase-based key (less secure)."
            )
            print("   Generate a key with: python scripts/generate_encryption_key.py")
            response = input("Continue anyway? (yes/no): ")
            if response.lower() != "yes":
                print("Migration cancelled.")
                return

        # Get all tokens
        tokens = session.query(Token).all()

        if not tokens:
            print("No tokens found in database. Nothing to migrate.")
            return

        print(f"Found {len(tokens)} tokens to migrate...")

        migrated = 0
        errors = 0

        for token in tokens:
            try:
                # Check if already encrypted (heuristic: encrypted tokens are longer)
                # This is not perfect, but works for migration
                if len(token._encrypted_access_token) > 200:
                    # Likely already encrypted, skip
                    print(
                        f"  ⏭️  Token for athlete {token.athlete_id} appears already encrypted"
                    )
                    continue

                # Encrypt tokens
                # Access the plain text tokens (if they're not encrypted yet)
                # We'll read from the column directly and encrypt
                plain_access = token._encrypted_access_token  # May be plain text
                plain_refresh = token._encrypted_refresh_token  # May be plain text

                # Encrypt them
                encrypted_access = encrypt_token(plain_access)
                encrypted_refresh = encrypt_token(plain_refresh)

                # Update
                token._encrypted_access_token = encrypted_access
                token._encrypted_refresh_token = encrypted_refresh

                migrated += 1
                print(f"  ✅ Encrypted tokens for athlete {token.athlete_id}")

            except Exception as e:
                errors += 1
                print(
                    f"  ❌ Error encrypting token for athlete {token.athlete_id}: {e}"
                )

        if migrated > 0:
            session.commit()
            print(f"\n✅ Migration complete: {migrated} tokens encrypted")

        if errors > 0:
            print(f"\n⚠️  {errors} tokens failed to encrypt")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Token Encryption Migration")
    print("=" * 60)
    print("\nThis will encrypt all existing tokens in the database.")
    print("Make sure TOKEN_ENCRYPTION_KEY is set in your environment.\n")

    response = input("Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Migration cancelled.")
        sys.exit(0)

    migrate_tokens()
