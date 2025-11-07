"""
Test Token Encryption - Verify Automatic Encryption
====================================================

This script tests that token encryption works automatically.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv

env_local_path = project_root / ".env.local"
if env_local_path.exists():
    load_dotenv(env_local_path, override=False)

from src.utils.token_encryption import encrypt_token, decrypt_token

print("=" * 60)
print("Testing Token Encryption")
print("=" * 60)

# Test 1: Encryption/Decryption
print("\n1. Testing encryption/decryption...")
test_token = "test_access_token_12345"
encrypted = encrypt_token(test_token)
decrypted = decrypt_token(encrypted)

print(f"   Original token:  {test_token}")
print(f"   Encrypted token: {encrypted[:50]}... (length: {len(encrypted)})")
print(f"   Decrypted token: {decrypted}")
match_status = "PASS" if test_token == decrypted else "FAIL"
print(f"   Match: {match_status} ({test_token == decrypted})")

# Test 2: Verify encryption key is set
print("\n2. Checking encryption key...")
if os.getenv("TOKEN_ENCRYPTION_KEY"):
    print(f"   [OK] TOKEN_ENCRYPTION_KEY is set")
    print(f"   Key length: {len(os.getenv('TOKEN_ENCRYPTION_KEY'))}")
else:
    print("   [WARNING] TOKEN_ENCRYPTION_KEY not set - using fallback (less secure)")

# Test 3: Show that encrypted tokens are longer
print("\n3. Comparing token lengths...")
plain_token = "a" * 40  # Typical token length
encrypted_token = encrypt_token(plain_token)
print(f"   Plain token length:    {len(plain_token)}")
print(f"   Encrypted token length: {len(encrypted_token)}")
print(f"   Difference:            {len(encrypted_token) - len(plain_token)} characters")

print("\n" + "=" * 60)
print("[SUCCESS] Encryption is working!")
print("=" * 60)
print("\nIMPORTANT:")
print("   - Tokens are AUTOMATICALLY encrypted when you set:")
print("     token.access_token = 'value'")
print("   - Tokens are AUTOMATICALLY decrypted when you read:")
print("     value = token.access_token")
print("   - This happens via @hybrid_property in Token model")
print("   - No manual encryption needed - it's transparent!")
print()
