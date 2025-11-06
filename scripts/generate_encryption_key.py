"""
Generate Encryption Key for Token Storage
=========================================

Generates a secure Fernet encryption key for token encryption.

Usage:
    python scripts/generate_encryption_key.py

Output:
    A base64-encoded Fernet key that can be stored in TOKEN_ENCRYPTION_KEY
    environment variable.

Security:
    - Store this key securely (environment variable, secrets manager)
    - Never commit this key to version control
    - Use different keys for staging and production
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.token_encryption import generate_encryption_key

if __name__ == "__main__":
    key = generate_encryption_key()
    print("\n" + "=" * 60)
    print("Generated Encryption Key")
    print("=" * 60)
    print(f"\nTOKEN_ENCRYPTION_KEY={key}\n")
    print("=" * 60)
    print("\nSECURITY WARNING:")
    print("   - Store this key securely (environment variable)")
    print("   - Never commit this key to version control")
    print("   - Use different keys for staging and production")
    print("   - Add TOKEN_ENCRYPTION_KEY to your .env.local for local development")
    print(
        "   - Add TOKEN_ENCRYPTION_KEY to Railway environment variables for production"
    )
    print("\n")
